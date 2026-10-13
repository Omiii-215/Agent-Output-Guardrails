import pytest

from backend.cases import service as cases
from backend.cases.models import CaseStatus
from backend.errors import Conflict, Forbidden


def _case(db, actor, title="Invoice INV-1"):
    with db.tenant(actor.organization_id, actor=actor) as tx:
        return cases.create_case(tx, actor, module="invoices", title=title).id


def test_case_lifecycle_follows_state_machine(db, acme_operator):
    case_id = _case(db, acme_operator)
    with db.tenant(acme_operator.organization_id, actor=acme_operator) as tx:
        case = cases.get_for_update(tx, case_id)
        cases.transition(tx, case, CaseStatus.READY_TO_EVALUATE)
        cases.transition(tx, case, CaseStatus.EVALUATING)
        cases.transition(tx, case, CaseStatus.IN_REVIEW)
        assert case.revision == 4
        with pytest.raises(Conflict) as err:
            cases.transition(tx, case, CaseStatus.ACTION_PENDING)
        assert err.value.code == "INVALID_TRANSITION"


def test_disabled_module_cannot_open_cases(db, acme_operator):
    with db.tenant(acme_operator.organization_id) as tx, pytest.raises(Forbidden) as err:
        cases.create_case(tx, acme_operator, module="aml", title="x")
    assert err.value.code == "MODULE_DISABLED"


def test_stale_revision_is_rejected(world, db, acme_operator):
    case_id = _case(db, acme_operator)
    operator = world.acme_as("operator")
    ok = operator.post(
        f"/v1/cases/{case_id}/assign",
        json={"owner_subject": "approver@acme.test", "expected_revision": 1},
    )
    assert ok.status_code == 200 and ok.json()["revision"] == 2
    stale = operator.post(
        f"/v1/cases/{case_id}/assign",
        json={"owner_subject": "operator@acme.test", "expected_revision": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "STALE_REVISION"


def test_queue_pagination_and_filters(world, db, acme_operator):
    ids = [_case(db, acme_operator, f"Invoice {i}") for i in range(5)]
    operator = world.acme_as("operator")
    first = operator.get("/v1/cases", params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = operator.get("/v1/cases", params={"limit": 2, "cursor": first["next_cursor"]}).json()
    third = operator.get("/v1/cases", params={"limit": 2, "cursor": second["next_cursor"]}).json()
    seen = [c["id"] for page in (first, second, third) for c in page["items"]]
    assert sorted(seen) == sorted(str(i) for i in ids)
    assert third["next_cursor"] is None
    filtered = operator.get("/v1/cases", params={"status": "IN_REVIEW"}).json()
    assert filtered["items"] == []


def test_queue_and_case_are_tenant_isolated(world, db, acme_operator):
    case_id = _case(db, acme_operator)
    globex = world.globex_as("operator")
    assert globex.get("/v1/cases").json()["items"] == []
    assert globex.get(f"/v1/cases/{case_id}").status_code == 404
    assert globex.get(f"/v1/cases/{case_id}/history").status_code == 404
    assert globex.post(f"/v1/cases/{case_id}/comments", json={"body": "hi"}).status_code == 404


def test_comments_close_and_history(world, db, acme_operator):
    case_id = _case(db, acme_operator)
    operator = world.acme_as("operator")
    assert (
        operator.post(f"/v1/cases/{case_id}/comments", json={"body": "Called vendor"}).status_code
        == 201
    )
    assert [c["body"] for c in operator.get(f"/v1/cases/{case_id}/comments").json()] == [
        "Called vendor"
    ]
    closed = operator.post(
        f"/v1/cases/{case_id}/close", json={"reason": "Withdrawn by vendor", "expected_revision": 1}
    )
    assert closed.json()["status"] == "CLOSED"
    actions = [e["action"] for e in operator.get(f"/v1/cases/{case_id}/history").json()]
    assert actions == ["case.created", "case.transitioned"]


def test_auditor_reads_but_cannot_change_cases(world, db, acme_operator):
    case_id = _case(db, acme_operator)
    auditor = world.acme_as("auditor")
    assert auditor.get(f"/v1/cases/{case_id}").status_code == 200
    resp = auditor.post(
        f"/v1/cases/{case_id}/close", json={"reason": "nope", "expected_revision": 1}
    )
    assert resp.status_code == 403


def test_module_registry_lists_eight_modules(world):
    modules = world.api.client.get("/v1/modules").json()
    assert len(modules) == 8
    enabled = {m["code"] for m in modules if m["enabled"]}
    assert enabled == {"invoices", "reconciliation", "payment_gateway"}
