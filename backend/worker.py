"""Job handler registry and the worker loop.

Handlers run on behalf of an organization with the system actor. Transactional
handlers use ``ctx.fenced()``, which verifies the lease inside the same
transaction as the handler's writes, so a worker whose lease was taken over
cannot commit stale work. Handlers must be idempotent: a job may run again
after a crash between its work and its completion.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from sqlalchemy import select

from backend.domain.clock import utcnow
from backend.errors import DomainError
from backend.identity.actor import system_actor
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.runtime import Runtime

log = logging.getLogger("finguard.worker")


@dataclass
class JobContext:
    runtime: Runtime
    job: jobs.ClaimedJob

    @property
    def actor(self):
        return system_actor(self.job.organization_id)

    @contextmanager
    def fenced(self) -> Iterator[TenantSession]:
        db = self.runtime.db
        with db.tenant(self.job.organization_id, actor=self.actor) as tx:
            yield tx
            jobs.assert_lease(tx.session, self.job)


Handler = Callable[[JobContext], None]


@dataclass
class JobRegistry:
    handlers: dict[str, Handler] = field(default_factory=dict)
    consumers: dict[str, list[str]] = field(default_factory=dict)  # event_type -> job types

    def handler(self, job_type: str) -> Callable[[Handler], Handler]:
        def register(fn: Handler) -> Handler:
            self.handlers[job_type] = fn
            return fn

        return register

    def consumer(self, event_type: str, name: str) -> Callable[[Handler], Handler]:
        job_type = f"event:{name}"
        self.consumers.setdefault(event_type, []).append(job_type)
        return self.handler(job_type)


registry = JobRegistry()


def dispatch_outbox(runtime: Runtime, limit: int = 100) -> int:
    """Turn committed outbox events into consumer jobs (one per consumer, deduplicated)."""
    db = runtime.db
    dispatched = 0
    with db.system() as session:
        events = session.scalars(
            select(jobs.OutboxEvent)
            .where(jobs.OutboxEvent.published_at.is_(None))
            .order_by(jobs.OutboxEvent.occurred_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).all()
        for event in events:
            for job_type in registry.consumers.get(event.event_type, []):
                existing = session.scalars(
                    select(jobs.Job).where(
                        jobs.Job.organization_id == event.organization_id,
                        jobs.Job.job_type == job_type,
                        jobs.Job.dedupe_key == str(event.id),
                    )
                ).first()
                if existing is None:
                    session.add(
                        jobs.Job(
                            organization_id=event.organization_id,
                            job_type=job_type,
                            object_ref=event.aggregate_id,
                            payload={"event_id": str(event.id), **event.data},
                            dedupe_key=str(event.id),
                        )
                    )
            event.published_at = utcnow()
            dispatched += 1
    return dispatched


def run_job(runtime: Runtime, job: jobs.ClaimedJob) -> str:
    handler = registry.handlers.get(job.job_type)
    if handler is None:
        return jobs.fail(runtime.db, job, code="NO_HANDLER", message=job.job_type, retryable=False)
    ctx = JobContext(runtime, job)
    try:
        handler(ctx)
        with runtime.db.system() as session:
            jobs.complete(session, job)
        return jobs.JobState.SUCCEEDED
    except jobs.LeaseLost:
        log.warning("lease lost for job %s (%s)", job.id, job.job_type)
        return "LEASE_LOST"
    except jobs.RetryableError as exc:
        return jobs.fail(runtime.db, job, code=exc.code, message=str(exc), retryable=True)
    except DomainError as exc:
        return jobs.fail(runtime.db, job, code=exc.code, message=exc.message, retryable=False)
    except Exception as exc:  # unexpected: retry with backoff, then dead-letter
        log.exception("job %s failed", job.id)
        return jobs.fail(runtime.db, job, code=type(exc).__name__, message=str(exc), retryable=True)


def run_once(runtime: Runtime, *, max_jobs: int = 1000) -> int:
    """Process available work until the queue is empty. Returns jobs processed."""
    processed = 0
    jobs.reap_expired(runtime.db)
    while processed < max_jobs:
        dispatch_outbox(runtime)
        job = jobs.claim(runtime.db, lease_seconds=runtime.settings.job_lease_seconds)
        if job is None:
            break
        run_job(runtime, job)
        processed += 1
    return processed


def run_forever(runtime: Runtime, *, idle_sleep: float = 1.0) -> None:  # pragma: no cover
    log.info("worker loop started")
    while True:
        if run_once(runtime, max_jobs=100) == 0:
            time.sleep(idle_sleep)
