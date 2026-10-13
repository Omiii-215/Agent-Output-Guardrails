import threading
import uuid

from sqlalchemy import func, select

from backend.actions import execution
from backend.actions.models import ActionIntent, SpendBucket
from backend.adapters.payments.simulator import SimulatedTransfer, encode_event, sign
from backend.worker import run_once
from tests.support import (
    approved_proposal,
    case_detail,
    create_intent,
    evaluate,
    intent_state,
    make_invoice,
    pg_only,
    run_jobs,
)


def transfers(db):
    with db.admin() as s:
        return s.scalar(select(func.count()).select_from(SimulatedTransfer))


def settle(world, intent, state="SETTLED"):
    resp = world.acme_as("admin").post(
        f"/v1/simulator/intents/{intent['id']}/advance", json={"state": state}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_approved_payment_executes_settles_and_links_outcome(world, runtime, db):
    detail, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    assert intent["simulated"] is True and intent["execution"]["state"] == "CREATED"
    run_once(runtime)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "ACCEPTED", state
    assert state["reservation"] == [{"amount_minor": "590000", "state": "COMMITTED"}]
    assert case_detail(world, detail["case"]["id"])["case"]["status"] == "ACTION_PENDING"

    assert settle(world, intent) == {"status": "accepted"}
    run_once(runtime)
    assert intent_state(world, intent)["execution"]["state"] == "SETTLED"
    assert case_detail(world, detail["case"]["id"])["case"]["status"] == "RESOLVED"
    history = [
        e["action"]
        for e in world.acme_as("auditor").get(f"/v1/cases/{detail['case']['id']}/history").json()
    ]
    assert "invoice.payment_recorded" in history and "intent.settled" in history

    # The same invoice submitted again is now a paid duplicate.
    again = make_invoice(world, detail["vendor"]["id"], number=detail["invoice"]["number"])
    assert evaluate(world, runtime, again["case_id"])["evaluation"]["outcome"] == "BLOCK"


def test_intent_accepts_no_financial_fields_and_needs_approval(world, runtime):
    from tests.support import propose, request_approval, reviewed_case

    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail)
    request = request_approval(world, proposal)
    resp = world.acme_as("operator").post(
        "/v1/action-intents",
        json={
            "proposal_id": proposal["id"],
            "approval_request_id": request["id"],
            "amount_minor": "1",
        },
    )
    assert resp.status_code == 422
    early = world.acme_as("operator").post(
        "/v1/action-intents",
        json={"proposal_id": proposal["id"], "approval_request_id": request["id"]},
    )
    assert early.status_code == 409 and early.json()["error"]["code"] == "NOT_APPROVED"


def test_repeated_intent_creation_is_one_logical_operation(world, runtime, db):
    _, proposal, request = approved_proposal(world, runtime)
    first = create_intent(world, proposal, request)
    second = create_intent(world, proposal, request)
    assert first["id"] == second["id"]
    run_once(runtime)
    run_once(runtime)
    assert transfers(db) == 1


def test_lost_response_holds_reservation_and_never_resubmits(world, runtime, db):
    _, proposal, request = approved_proposal(world, runtime)
    runtime.payments.plan = ["TIMEOUT_AFTER"]
    intent = create_intent(world, proposal, request)
    run_jobs(runtime, execution.RESERVE_JOB, execution.EXECUTE_JOB)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "UNKNOWN"
    assert state["reservation"][0]["state"] == "ACTIVE"
    run_once(runtime)  # status reconciliation
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "ACCEPTED"
    assert [h["kind"] for h in state["provider"]["history"]] == ["SUBMIT", "STATUS"]
    assert transfers(db) == 1


def test_timeout_before_acceptance_is_confirmed_failed_and_released(world, runtime, db):
    detail, proposal, request = approved_proposal(world, runtime)
    runtime.payments.plan = ["TIMEOUT_BEFORE"]
    intent = create_intent(world, proposal, request)
    run_once(runtime)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "FAILED"
    assert state["reservation"][0]["state"] == "RELEASED"
    assert transfers(db) == 0
    assert case_detail(world, detail["case"]["id"])["case"]["status"] == "IN_REVIEW"


def test_provider_rejection_releases_spend(world, runtime, db):
    _, proposal, request = approved_proposal(world, runtime)
    runtime.payments.plan = ["REJECT"]
    intent = create_intent(world, proposal, request)
    run_once(runtime)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "FAILED"
    with db.admin() as s:
        bucket = s.scalars(select(SpendBucket)).one()
    assert (bucket.reserved_minor, bucket.committed_minor) == (0, 0)


def test_crash_after_claim_goes_to_unknown_not_resubmission(world, runtime, db):
    _, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    run_jobs(runtime, execution.RESERVE_JOB)
    with db.tenant(world.acme) as tx:  # simulate: claimed, then the worker died
        execution.claim(tx, uuid.UUID(intent["id"]))
    run_jobs(runtime, execution.EXECUTE_JOB)
    assert intent_state(world, intent)["execution"]["state"] == "UNKNOWN"
    run_once(runtime)
    assert intent_state(world, intent)["execution"]["state"] == "FAILED"  # never sent
    assert transfers(db) == 0


def test_webhook_signature_duplicates_and_ordering(world, runtime):
    _, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    run_once(runtime)
    client = world.api.client
    event = runtime.payments.advance(world.acme, intent["provider"]["idempotency_key"], "SETTLED")
    raw = encode_event(event)
    bad = client.post(
        "/v1/webhooks/simulator", content=raw, headers={"X-Simulator-Signature": sign("wrong", raw)}
    )
    assert bad.status_code == 401
    good = {"X-Simulator-Signature": runtime.payments.sign(raw)}
    assert client.post("/v1/webhooks/simulator", content=raw, headers=good).json() == {
        "status": "accepted"
    }
    assert client.post("/v1/webhooks/simulator", content=raw, headers=good).json() == {
        "status": "duplicate"
    }
    run_once(runtime)
    assert intent_state(world, intent)["execution"]["state"] == "SETTLED"
    # A late failure event after settlement does not regress the state.
    late = {**event, "event_id": "evt_late", "type": "transfer.failed"}
    raw = encode_event(late)
    client.post(
        "/v1/webhooks/simulator",
        content=raw,
        headers={"X-Simulator-Signature": runtime.payments.sign(raw)},
    )
    run_once(runtime)
    assert intent_state(world, intent)["execution"]["state"] == "SETTLED"


def test_emergency_stop_prevents_new_claims(world, runtime):
    _, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    run_jobs(runtime, execution.RESERVE_JOB)
    world.acme_as("approver").post(
        "/v1/actions/emergency-stop", json={"halted": True, "reason": "Fraud alert"}
    )
    run_once(runtime)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "INVALIDATED"
    assert state["execution"]["reason"] == "EMERGENCY_STOP"
    assert state["reservation"][0]["state"] == "RELEASED"


def test_payee_change_before_submission_invalidates_intent(world, runtime):
    detail, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    run_jobs(runtime, execution.RESERVE_JOB)
    world.acme_as("operator").post(
        f"/v1/vendors/{detail['vendor']['id']}/beneficiaries",
        json={
            "account_holder": "Mallory Traders",
            "account_number": "999988887777",
            "ifsc": "SBIN0000009",
        },
    )
    run_once(runtime)
    state = intent_state(world, intent)
    assert state["execution"]["state"] == "INVALIDATED"
    assert state["reservation"][0]["state"] == "RELEASED"


def test_revoked_approver_blocks_intent(world, runtime):
    _, proposal, request = approved_proposal(world, runtime)
    admin = world.acme_as("admin")
    member = next(
        m for m in admin.get("/v1/members").json() if m["identity_subject"] == "approver@acme.test"
    )
    admin.patch(f"/v1/members/{member['id']}", json={"status": "REVOKED", "reason": "Left"})
    resp = world.acme_as("operator").post(
        "/v1/action-intents",
        json={"proposal_id": proposal["id"], "approval_request_id": request["id"]},
    )
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "APPROVER_REVOKED"


def test_intents_are_tenant_isolated(world, runtime):
    _, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    globex = world.globex_as("operator")
    assert globex.get(f"/v1/action-intents/{intent['id']}").status_code == 404
    assert (
        globex.post(
            "/v1/action-intents",
            json={"proposal_id": proposal["id"], "approval_request_id": request["id"]},
        ).status_code
        == 404
    )


@pg_only
def test_concurrent_reservations_cannot_overspend(world, runtime, db):
    from backend.actions.templates import PAYMENT_PREFLIGHT

    # Daily limit fits one 5,900.00 payment but not two.
    doc = {
        **PAYMENT_PREFLIGHT,
        "spend_limits": [{"currency": "INR", "window": "DAY", "limit_minor": 900_000}],
    }
    doc["scenarios"] = [s for s in doc["scenarios"] if s["name"] != "over limit blocks"]
    author, publisher = world.acme_as("author"), world.acme_as("publisher")
    pid = author.post("/v1/policies", json={"document": doc}).json()["id"]
    author.post(f"/v1/policies/{pid}/validate")
    publisher.post(f"/v1/policies/{pid}/publish", json={"reason": "Lower limit"})
    run_once(runtime)

    approved = [
        approved_proposal(world, runtime, vendor_name=name)[1:]
        for name in ("Alpha Steel", "Beta Steel")
    ]
    intents = [uuid.UUID(create_intent(world, p, r)["id"]) for p, r in approved]

    barrier = threading.Barrier(2)

    def reserve(intent_id):
        barrier.wait()
        with db.tenant(world.acme) as tx:
            execution.reserve(tx, intent_id, created_by="test")

    threads = [threading.Thread(target=reserve, args=(i,)) for i in intents]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with db.admin() as s:
        states = sorted(s.get(ActionIntent, (world.acme, i)).state for i in intents)
        bucket = s.scalars(select(SpendBucket)).one()
    assert states == ["INVALIDATED", "RESERVED"]
    assert bucket.reserved_minor == 590_000 <= bucket.limit_minor
