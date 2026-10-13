from backend.domain.canonical import digest
from backend.worker import run_once
from tests.support import case_detail, proposal_body, propose, reviewed_case


def test_proposal_is_frozen_with_server_digest_and_preflighted(world, runtime):
    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail)
    assert proposal["state"] == "READY_FOR_APPROVAL", proposal["preflight"]
    assert proposal["simulated"] is True
    assert proposal["digest"] == digest(proposal["payload"])
    assert proposal["payload"]["amount_minor"] == "590000"
    assert "account_number" not in str(proposal["payload"])
    assert proposal["preflight"]["outcome"] == "PASS"
    case = case_detail(world, detail["case"]["id"])
    assert case["proposals"][0]["id"] == proposal["id"]


def test_client_cannot_supply_a_digest(world, runtime):
    detail = reviewed_case(world, runtime)
    body = proposal_body(detail, digest="sha256:" + "0" * 64)
    resp = world.acme_as("operator").post("/v1/action-proposals", json=body)
    assert resp.status_code == 422
    assert resp.json()["detail"][0]["type"] == "extra_forbidden"


def test_amount_payee_and_mode_are_validated(world, runtime):
    detail = reviewed_case(world, runtime)
    operator = world.acme_as("operator")
    wrong_amount = operator.post(
        "/v1/action-proposals",
        json=proposal_body(detail, amount={"amount_minor": "590001", "currency": "INR"}),
    )
    assert wrong_amount.json()["error"]["code"] == "AMOUNT_MISMATCH"
    live = operator.post("/v1/action-proposals", json=proposal_body(detail, mode="LIVE"))
    assert live.json()["error"]["code"] == "MODE_NOT_ALLOWED"
    other_payee = operator.post(
        "/v1/action-proposals",
        json=proposal_body(detail, beneficiary_version_id="00000000-0000-0000-0000-000000000000"),
    )
    assert other_payee.json()["error"]["code"] == "BENEFICIARY_NOT_CURRENT"


def test_only_one_active_proposal_per_case(world, runtime):
    detail = reviewed_case(world, runtime)
    propose(world, runtime, detail)
    again = world.acme_as("operator").post("/v1/action-proposals", json=proposal_body(detail))
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "PROPOSAL_EXISTS"


def test_unresolved_findings_prevent_proposals(world, runtime):
    from tests.support import evaluate, make_invoice, make_vendor

    vendor_id, _ = make_vendor(world)
    make_invoice(world, vendor_id, number="DUP-1")
    second = make_invoice(world, vendor_id, number="DUP-1")
    detail = evaluate(world, runtime, second["case_id"])
    assert detail["evaluation"]["outcome"] == "REVIEW"
    resp = world.acme_as("operator").post("/v1/action-proposals", json=proposal_body(detail))
    assert resp.json()["error"]["code"] == "EVALUATION_NOT_ELIGIBLE"


def test_material_change_makes_proposal_stale(world, runtime):
    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail)
    world.acme_as("operator").patch(
        f"/v1/invoices/{detail['invoice']['id']}",
        json={
            "expected_revision": case_detail(world, detail["case"]["id"])["case"]["revision"],
            "fields": {"po_number": "PO-78"},
            "reason": "PO corrected",
        },
    )
    refreshed = world.acme_as("operator").get(f"/v1/action-proposals/{proposal['id']}").json()
    assert refreshed["state"] == "STALE"
    assert "Material input changed" in refreshed["state_reason"]


def test_emergency_stop_blocks_preflight(world, runtime):
    detail = reviewed_case(world, runtime)
    assert (
        world.acme_as("operator")
        .post("/v1/actions/emergency-stop", json={"halted": True, "reason": "test"})
        .status_code
        == 403
    )
    halted = world.acme_as("admin").post(
        "/v1/actions/emergency-stop", json={"halted": True, "reason": "Suspected compromise"}
    )
    assert halted.json()["halted"] is True
    proposal = propose(world, runtime, detail)
    assert proposal["state"] == "BLOCKED"
    reasons = {f["reason_code"] for f in proposal["preflight"]["findings"] if f["effect"]}
    assert reasons == {"EMERGENCY_STOP"}


def test_agent_service_account_can_propose_but_not_approve(world, runtime):
    detail = reviewed_case(world, runtime)
    token = (
        world.acme_as("admin")
        .post(
            "/v1/service-accounts",
            json={"name": "AP agent", "scopes": ["proposal.create", "case.read"]},
        )
        .json()["token"]
    )
    headers = {"Authorization": f"Bearer {token}"}
    resp = world.api.client.post(
        "/v1/action-proposals", json=proposal_body(detail), headers=headers
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["maker_actor_type"] == "service"
    run_once(runtime)


def test_proposals_are_tenant_isolated(world, runtime):
    detail = reviewed_case(world, runtime)
    proposal = propose(world, runtime, detail)
    globex = world.globex_as("operator")
    assert globex.get(f"/v1/action-proposals/{proposal['id']}").status_code == 404
    assert globex.post("/v1/action-proposals", json=proposal_body(detail)).status_code == 404
