import threading
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from backend.domain.clock import utcnow
from backend.errors import Conflict, InvalidInput
from backend.persistence import idempotency, jobs
from backend.persistence.jobs import Job, JobState
from backend.telemetry import audit
from backend.telemetry.audit import AuditEvent
from backend.worker import JobContext, dispatch_outbox, registry, run_job, run_once
from tests.support import pg_only

calls: list[str] = []


@registry.handler("test.record")
def _record(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        audit.record(tx, "test.handled", object_type="job", object_id=ctx.job.id)
    calls.append(ctx.job.payload.get("tag", ""))


@registry.handler("test.flaky")
def _flaky(ctx: JobContext) -> None:
    raise jobs.RetryableError("provider timeout", code="PROVIDER_TIMEOUT")


@registry.handler("test.invalid")
def _invalid(ctx: JobContext) -> None:
    raise InvalidInput("bad mapping")


@registry.consumer("test.happened", "test-consumer")
def _consume(ctx: JobContext) -> None:
    calls.append(f"consumed:{ctx.job.payload['event_id']}")


@pytest.fixture(autouse=True)
def _reset_calls():
    calls.clear()


def _job(db, job_id) -> Job:
    with db.admin() as s:
        return s.get(Job, job_id)


def test_job_commits_with_business_change_or_not_at_all(db, two_orgs):
    org, _ = two_orgs
    with pytest.raises(RuntimeError), db.tenant(org) as tx:
        jobs.enqueue(tx, "test.record")
        raise RuntimeError("business validation failed")
    with db.admin() as s:
        assert s.scalars(select(Job)).all() == []


def test_job_runs_once_and_dedupes(db, two_orgs, runtime):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        first = jobs.enqueue(tx, "test.record", payload={"tag": "a"}, dedupe_key="doc-1")
        again = jobs.enqueue(tx, "test.record", payload={"tag": "b"}, dedupe_key="doc-1")
    assert first.id == again.id
    assert run_once(runtime) == 1
    assert calls == ["a"]
    assert _job(db, first.id).state == JobState.SUCCEEDED


def test_retryable_failures_back_off_then_dead_letter(db, two_orgs, runtime):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        job_id = jobs.enqueue(tx, "test.flaky", max_attempts=2).id
    run_once(runtime)
    job = _job(db, job_id)
    assert job.state == JobState.READY and job.attempts == 1
    assert job.available_at > utcnow()
    assert job.last_error_code == "PROVIDER_TIMEOUT"
    with db.admin() as s:
        s.execute(update(Job).where(Job.id == job_id).values(available_at=utcnow()))
    run_once(runtime)
    assert _job(db, job_id).state == JobState.DEAD


def test_invalid_input_is_not_retried(db, two_orgs, runtime):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        job_id = jobs.enqueue(tx, "test.invalid").id
    run_once(runtime)
    job = _job(db, job_id)
    assert job.state == JobState.DEAD and job.attempts == 1


def test_expired_lease_cannot_commit_and_job_is_reaped(db, two_orgs, runtime):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        job_id = jobs.enqueue(tx, "test.record").id
    claimed = jobs.claim(db)
    with db.admin() as s:
        s.execute(
            update(Job).where(Job.id == job_id).values(lease_until=utcnow() - timedelta(seconds=1))
        )
    # The slow worker finishes after its lease expired: its writes roll back.
    assert run_job(runtime, claimed) == "LEASE_LOST"
    with db.admin() as s:
        assert s.scalars(select(AuditEvent).where(AuditEvent.action == "test.handled")).all() == []
    assert jobs.reap_expired(db) == 1
    assert _job(db, job_id).state == JobState.READY
    run_once(runtime)
    assert _job(db, job_id).state == JobState.SUCCEEDED


def test_work_survives_a_restart(db, two_orgs, app, pg_urls, tmp_path):
    from backend.config import Settings
    from backend.persistence.database import Database
    from backend.runtime import build_runtime

    org, _ = two_orgs
    with db.tenant(org) as tx:
        jobs.enqueue(tx, "test.record", payload={"tag": "after-restart"})
    # A fresh process: new engine, new runtime, same database.
    fresh_db = Database(db.url, admin_url=db.admin_url)
    fresh = build_runtime(Settings(env="test", object_store_path=tmp_path), fresh_db)
    assert run_once(fresh) == 1
    assert calls == ["after-restart"]
    fresh_db.dispose()


def test_outbox_events_reach_each_consumer_once(db, two_orgs, runtime):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        event = jobs.emit(tx, "test.happened", aggregate_id=uuid.uuid4(), aggregate_revision=3)
    assert dispatch_outbox(runtime) == 1
    assert dispatch_outbox(runtime) == 0  # already published
    run_once(runtime)
    assert calls == [f"consumed:{event.id}"]


@pg_only
def test_concurrent_workers_claim_distinct_jobs(db, two_orgs):
    org, _ = two_orgs
    with db.tenant(org) as tx:
        for i in range(20):
            jobs.enqueue(tx, "test.record", payload={"tag": str(i)})
    claimed: list[uuid.UUID] = []
    lock = threading.Lock()

    def worker():
        while (job := jobs.claim(db)) is not None:
            with lock:
                claimed.append(job.id)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(claimed) == 20 and len(set(claimed)) == 20


def test_idempotency_replays_and_detects_conflicts(db, world, acme_operator):
    runs: list[int] = []

    def op(tx):
        runs.append(1)
        audit.record(tx, "test.op", object_type="x", object_id=None)
        return 201, {"id": "abc", "n": 1}

    first = idempotency.run(
        db, acme_operator, route="POST /t", key="key-12345", body={"a": 1}, operation=op
    )
    second = idempotency.run(
        db, acme_operator, route="POST /t", key="key-12345", body={"a": 1}, operation=op
    )
    assert first.body == second.body and second.replayed and len(runs) == 1
    with pytest.raises(Conflict) as err:
        idempotency.run(
            db, acme_operator, route="POST /t", key="key-12345", body={"a": 2}, operation=op
        )
    assert err.value.code == "IDEMPOTENCY_CONFLICT"


@pg_only
def test_concurrent_identical_requests_converge(db, world, acme_operator):
    runs: list[int] = []
    barrier = threading.Barrier(4)
    results = []

    def op(tx):
        runs.append(1)
        return 201, {"ok": True}

    def call():
        barrier.wait()
        results.append(
            idempotency.run(
                db, acme_operator, route="POST /c", key="same-key-1", body={}, operation=op
            )
        )

    threads = [threading.Thread(target=call) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(runs) == 1
    assert len(results) == 4 and sum(not r.replayed for r in results) == 1


def test_operations_api_is_scoped_and_retries_dead_jobs(world, db, runtime):
    with db.tenant(world.acme) as tx:
        job_id = jobs.enqueue(tx, "test.invalid").id
    with db.tenant(world.globex) as tx:
        jobs.enqueue(tx, "test.record")
    run_once(runtime)
    admin = world.acme_as("admin")
    listed = admin.get("/v1/operations/jobs").json()
    assert [j["id"] for j in listed] == [str(job_id)]
    assert listed[0]["state"] == "DEAD"
    retried = admin.post(f"/v1/operations/jobs/{job_id}/retry")
    assert retried.json()["state"] == "READY"
    assert world.globex_as("admin").post(f"/v1/operations/jobs/{job_id}/retry").status_code == 404
    assert world.acme_as("operator").get("/v1/operations/jobs").status_code == 403
