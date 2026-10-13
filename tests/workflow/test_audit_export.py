import json
from datetime import timedelta

from sqlalchemy import update

from backend.audit.exports import AuditExport
from backend.domain.canonical import digest
from backend.domain.clock import utcnow
from backend.worker import run_once
from tests.support import approved_proposal, create_intent


def full_flow(world, runtime):
    detail, proposal, request = approved_proposal(world, runtime)
    intent = create_intent(world, proposal, request)
    run_once(runtime)
    world.acme_as("operator").post(
        f"/v1/simulator/intents/{intent['id']}/advance", json={"state": "SETTLED"}
    )
    run_once(runtime)
    return detail


def export(world, runtime, case_ids, persona="auditor"):
    resp = world.acme_as(persona).post(
        "/v1/audit-exports",
        json={"purpose": "Q3 internal audit sample", "case_ids": case_ids},
    )
    assert resp.status_code == 202, resp.text
    run_once(runtime)
    return resp.json()


def test_export_reconstructs_the_decision_without_restricted_data(world, runtime):
    detail = full_flow(world, runtime)
    requested = export(world, runtime, [detail["case"]["id"]])
    auditor = world.acme_as("auditor")
    status = auditor.get(f"/v1/audit-exports/{requested['id']}").json()
    assert status["state"] == "READY" and status["case_count"] == 1

    raw = auditor.get(f"/v1/audit-exports/{requested['id']}/download")
    bundle = json.loads(raw.content)
    case = bundle["cases"][0]
    assert case["case"]["status"] == "RESOLVED"
    assert {e["kind"] for e in case["evaluations"]} == {"DOCUMENT", "ACTION", "EXECUTION"}
    assert case["snapshots"] and case["policy_versions"]
    assert case["approval_decisions"][0]["actor_subject"] == "approver@acme.test"
    assert case["intents"][0]["state"] == "SETTLED"
    actions = {e["action"] for e in case["audit_events"]}
    assert {"proposal.created", "approval.approved", "intent.settled"} <= actions

    text = raw.text
    assert "123456789012" not in text
    assert "hmac:" not in text  # keyed account fingerprints are excluded
    assert "gAAAA" not in text  # no Fernet ciphertexts
    body = {k: v for k, v in bundle.items() if k != "bundle_digest"}
    assert digest(body) == bundle["bundle_digest"] == status["bundle_digest"]

    history = (
        world.acme_as("auditor")
        .get("/v1/audit/events", params={"action": "audit_export.downloaded"})
        .json()
    )
    assert len(history) == 1


def test_export_permissions_scope_and_expiry(world, runtime, db):
    detail = full_flow(world, runtime)
    case_id = detail["case"]["id"]
    assert (
        world.acme_as("operator")
        .post("/v1/audit-exports", json={"purpose": "curious operator", "case_ids": [case_id]})
        .status_code
        == 403
    )
    assert (
        world.globex_as("approver")
        .post("/v1/audit-exports", json={"purpose": "cross-tenant probe", "case_ids": [case_id]})
        .status_code
        == 404
    )
    requested = export(world, runtime, [case_id])
    assert (
        world.globex_as("approver").get(f"/v1/audit-exports/{requested['id']}/download").status_code
        == 404
    )
    with db.admin() as s:
        s.execute(update(AuditExport).values(expires_at=utcnow() - timedelta(minutes=1)))
    resp = world.acme_as("auditor").get(f"/v1/audit-exports/{requested['id']}/download")
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "EXPORT_EXPIRED"


def test_gated_modules_expose_contracts_but_no_results(world):
    client = world.api.client
    aml = client.get("/v1/modules/aml").json()
    assert aml["enabled"] is False
    assert "alert_id" in aml["contract"]["input_schema"]["properties"]
    assert "not a finding of money laundering" in aml["contract"]["boundary"]
    assert client.get("/v1/modules/nope").status_code == 404
    invoices = client.get("/v1/modules/invoices").json()
    assert invoices["enabled"] is True and invoices["contract"] is None
