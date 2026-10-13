from datetime import timedelta

from sqlalchemy import update

from backend.approvals.models import ApprovalRequest
from backend.domain.clock import utcnow
from tests.support import (
    add_member,
    approved_proposal,
    case_detail,
    decide,
    propose,
    request_approval,
    reviewed_case,
)


def test_independent_approval_moves_case_to_ready_for_action(world, runtime):
    detail, proposal, request = approved_proposal(world, runtime)
    assert request["state"] == "APPROVED"
    assert request["action_digest"] == proposal["digest"]
    case = case_detail(world, detail["case"]["id"])
    assert case["case"]["status"] == "READY_FOR_ACTION"
    assert case["proposals"][0]["state"] == "APPROVED"
    assert case["proposals"][0]["approval"]["decisions"][0]["actor_subject"] == "approver@acme.test"


def test_maker_cannot_approve_own_proposal(world, runtime, db):
    add_member(
        db,
        world.acme,
        "both@acme.test",
        ["finance_operator", "finance_approver"],
        limit_minor=10**12,
    )
    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail, persona="both")
    request = request_approval(world, proposal, persona="both")
    resp = world.api.as_("both@acme.test", world.acme).post(
        f"/v1/approval-requests/{request['id']}/decisions",
        json={"decision": "APPROVE", "reason": "mine", "expected_revision": request["revision"]},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SELF_APPROVAL"


def test_operator_and_admin_cannot_approve(world, runtime):
    detail = reviewed_case(world, runtime)
    request = request_approval(world, propose(world, runtime, detail))
    for persona in ("operator", "admin", "auditor"):
        assert decide(world, request, persona=persona).status_code == 403


def test_authority_limit_and_tiers(world, runtime):
    # 1,20,000.00 INR exceeds the 1,00,000 tier: two approvals required.
    lines = [
        {"description": "Machinery", "quantity": "1", "unit_price": "120000.00", "tax_rate": "0"}
    ]
    detail = reviewed_case(world, runtime, total="120000.00", lines=lines)
    request = request_approval(world, propose(world, runtime, detail))
    assert request["required_count"] == 2
    low = decide(world, request, persona="approver2")  # limit 50,000.00
    assert low.status_code == 403 and low.json()["error"]["code"] == "AUTHORITY_LIMIT"
    first = decide(world, request).json()
    assert first["state"] == "PENDING" and first["approved_count"] == 1
    again = decide(world, request)
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_DECIDED"
    add_member(
        world.api.client.app.state.db,
        world.acme,
        "cfo@acme.test",
        ["finance_approver"],
        limit_minor=10**12,
    )
    second = decide(world, request, persona="cfo")
    assert second.json()["state"] == "APPROVED"


def test_rejection_is_terminal(world, runtime):
    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail)
    request = request_approval(world, proposal)
    rejected = decide(world, request, decision="REJECT", reason="Wrong cost centre").json()
    assert rejected["state"] == "REJECTED"
    assert rejected["proposal"]["state"] == "REJECTED"


def test_changed_input_after_approval_invalidates_it(world, runtime):
    detail, _, request = approved_proposal(world, runtime)
    world.acme_as("operator").post(
        f"/v1/vendors/{detail['vendor']['id']}/beneficiaries",
        json={
            "account_holder": "Other Payee",
            "account_number": "555566667777",
            "ifsc": "SBIN0000002",
        },
    )
    refreshed = world.acme_as("approver").get(f"/v1/approval-requests/{request['id']}").json()
    assert refreshed["state"] == "STALE"
    assert refreshed["proposal"]["state"] == "STALE"
    case = case_detail(world, detail["case"]["id"])
    assert case["case"]["status"] == "READY_TO_EVALUATE"


def test_expired_request_cannot_be_approved(world, runtime, db):
    detail = reviewed_case(world, runtime)
    request = request_approval(world, propose(world, runtime, detail))
    with db.admin() as s:
        s.execute(update(ApprovalRequest).values(expires_at=utcnow() - timedelta(minutes=1)))
    resp = decide(world, request)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "APPROVAL_EXPIRED"
    assert (
        world.acme_as("approver").get(f"/v1/approval-requests/{request['id']}").json()["state"]
        == "EXPIRED"
    )


def test_new_payment_policy_requires_reapproval(world, runtime):
    from backend.actions.templates import PAYMENT_PREFLIGHT
    from backend.worker import run_once

    detail, _, request = approved_proposal(world, runtime)
    author, publisher = world.acme_as("author"), world.acme_as("publisher")
    doc = {**PAYMENT_PREFLIGHT, "approval": {**PAYMENT_PREFLIGHT["approval"], "count": 2}}
    pid = author.post("/v1/policies", json={"document": doc}).json()["id"]
    author.post(f"/v1/policies/{pid}/validate")
    assert (
        publisher.post(f"/v1/policies/{pid}/publish", json={"reason": "Dual control"}).status_code
        == 201
    )
    run_once(runtime)
    refreshed = world.acme_as("approver").get(f"/v1/approval-requests/{request['id']}").json()
    assert refreshed["state"] == "STALE"
    assert case_detail(world, detail["case"]["id"])["case"]["status"] == "IN_REVIEW"


def test_approval_inbox_is_tenant_scoped(world, runtime):
    detail = reviewed_case(world, runtime)
    request = request_approval(world, propose(world, runtime, detail))
    assert [r["id"] for r in world.acme_as("approver").get("/v1/approval-requests").json()] == [
        request["id"]
    ]
    assert world.globex_as("approver").get("/v1/approval-requests").json() == []
    assert decide_as_globex(world, request).status_code == 404


def decide_as_globex(world, request):
    return world.globex_as("approver").post(
        f"/v1/approval-requests/{request['id']}/decisions",
        json={"decision": "APPROVE", "reason": "probe", "expected_revision": 1},
    )
