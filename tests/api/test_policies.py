import uuid

import pytest

from backend.cases import service as cases
from backend.errors import Conflict, Forbidden
from backend.evidence.service import record_evidence
from backend.persistence.jobs import OutboxEvent
from backend.policies import service as policies
from backend.policies.models import Finding
from tests.unit.test_policy_engine import AMOUNT  # registers test rules

DOC = {
    "policy_code": "test-policy",
    "module": "invoices",
    "rules": [{**AMOUNT, "on_fail": "REVIEW"}],
    "scenarios": [{"name": "equal", "inputs": {"a": "1", "b": "1"}, "expected_outcome": "PASS"}],
}


def _publish(world, document=DOC):
    author, publisher = world.acme_as("author"), world.acme_as("publisher")
    draft = author.post("/v1/policies", json={"document": document})
    assert draft.status_code == 201, draft.text
    pid = draft.json()["id"]
    assert author.post(f"/v1/policies/{pid}/validate").json()["lifecycle"] == "VALIDATED"
    published = publisher.post(f"/v1/policies/{pid}/publish", json={"reason": "Q4 controls"})
    assert published.status_code == 201, published.text
    return published.json()


def test_policy_lifecycle_requires_independent_publisher(world, db):
    author = world.acme_as("author")
    pid = author.post("/v1/policies", json={"document": DOC}).json()["id"]
    author.post(f"/v1/policies/{pid}/validate")
    self_publish = world.api.as_("author@acme.test", world.acme).post(
        f"/v1/policies/{pid}/publish", json={"reason": "mine"}
    )
    assert self_publish.status_code == 403  # author lacks the publish capability entirely

    first = world.acme_as("publisher").post(
        f"/v1/policies/{pid}/publish", json={"reason": "go live"}
    )
    assert first.status_code == 201, first.text
    assert first.json()["lifecycle"] == "PUBLISHED"
    second = _publish(world)
    assert second["version"] == 2
    listed = {
        p["version"]: p["lifecycle"]
        for p in author.get("/v1/policies").json()
        if p["policy_code"] == "test-policy"
    }
    assert listed == {1: "RETIRED", 2: "PUBLISHED"}
    with db.admin() as s:
        events = s.query(OutboxEvent).filter_by(event_type="policy.published").all()
        assert sum(e.data["policy_code"] == "test-policy" for e in events) == 2


def test_same_person_with_both_roles_cannot_publish_own_policy(world, db, acme_operator):
    from tests.support import actor_for, add_member

    add_member(db, world.acme, "both@acme.test", ["policy_author", "policy_publisher"])
    both = actor_for(db, "both@acme.test", world.acme)
    with db.tenant(world.acme, actor=both) as tx:
        draft = policies.create_draft(tx, both, DOC)
        policies.validate(tx, both, draft.id)
    with pytest.raises(Forbidden) as err, db.tenant(world.acme, actor=both) as tx:
        policies.publish(tx, both, draft.id, "self")
    assert err.value.code == "SELF_PUBLISH"


def test_invalid_policy_and_failing_scenarios_are_rejected(world):
    author = world.acme_as("author")
    bad = {**DOC, "rules": [{"code": "nope.rule", "version": 1, "on_fail": "BLOCK"}]}
    pid = author.post("/v1/policies", json={"document": bad}).json()["id"]
    resp = author.post(f"/v1/policies/{pid}/validate")
    assert resp.status_code == 422 and "Unknown rule" in resp.json()["error"]["details"][0]

    failing = {
        **DOC,
        "scenarios": [{"name": "s", "inputs": {"a": "1", "b": "9"}, "expected_outcome": "PASS"}],
    }
    pid = author.post("/v1/policies", json={"document": failing}).json()["id"]
    resp = author.post(f"/v1/policies/{pid}/validate")
    assert resp.status_code == 422
    assert resp.json()["error"]["details"] == ["s: expected PASS, got REVIEW"]


def test_simulation_does_not_store_anything(world):
    author = world.acme_as("author")
    pid = author.post("/v1/policies", json={"document": DOC}).json()["id"]
    sim = author.post(f"/v1/policies/{pid}/simulate", json={"inputs": {"a": 3, "b": 9}}).json()
    assert sim["outcome"] == "REVIEW"
    assert sim["findings"][0]["observed"] == {"diff": "6"}


def _evaluated_case(db, world, acme_operator, inputs):
    with db.tenant(world.acme, actor=acme_operator) as tx:
        case = cases.create_case(tx, acme_operator, module="invoices", title="Test")
        policy = policies.active_policy(tx, "test-policy")
        evaluation = policies.record_evaluation(
            tx,
            case=case,
            kind="DOCUMENT",
            inputs=inputs,
            source_revision_map={"invoice": 1},
            policy=policy,
            created_by=acme_operator.subject,
        )
        return case.id, evaluation.id


def test_evaluations_are_reproducible_from_snapshots(world, db, acme_operator):
    _publish(world)
    _, evaluation_id = _evaluated_case(db, world, acme_operator, {"a": 10, "b": 12})
    with db.tenant(world.acme) as tx:
        replayed = policies.replay(tx, evaluation_id)
        stored = policies.findings_for(tx, evaluation_id)
    assert replayed.outcome.value == "REVIEW"
    assert stored[0].finding.observed == {"diff": "2"}


def test_finding_resolution_rules(world, db, acme_operator):
    _publish(world)
    _, evaluation_id = _evaluated_case(db, world, acme_operator, {"a": 1, "b": 2})
    with db.tenant(world.acme) as tx:
        finding_id = policies.findings_for(tx, evaluation_id)[0].finding.id

    approver = world.acme_as("approver")
    resolved = approver.post(
        f"/v1/findings/{finding_id}/resolutions",
        json={"resolution_code": "LEGITIMATE_DIFFERENCE", "reason": "Rounding agreed"},
    )
    assert resolved.status_code == 201
    with db.tenant(world.acme) as tx:
        from backend.policies.models import Evaluation

        assert policies.unresolved_blockers(tx, tx.get(Evaluation, evaluation_id)) == []

    # A newer evaluation supersedes earlier findings.
    _, newer = _evaluated_case(db, world, acme_operator, {"a": 1, "b": 3})
    with db.tenant(world.acme) as tx:
        newer_finding = policies.findings_for(tx, newer)[0].finding.id
    # The maker of the case cannot resolve its findings.
    with db.tenant(world.acme, actor=acme_operator) as tx, pytest.raises(Forbidden):
        policies.resolve_finding(
            tx, acme_operator, newer_finding, resolution_code="OK_OK", reason="mine"
        )
    assert (
        world.globex_as("approver")
        .post(
            f"/v1/findings/{newer_finding}/resolutions",
            json={"resolution_code": "OK_OK", "reason": "probe"},
        )
        .status_code
        == 404
    )


def test_block_findings_cannot_be_resolved(world, db, acme_operator):
    _publish(world, {**DOC, "rules": [{**AMOUNT, "on_fail": "BLOCK"}]})
    _, evaluation_id = _evaluated_case(db, world, acme_operator, {"a": 1, "b": 2})
    with db.tenant(world.acme) as tx:
        finding = policies.findings_for(tx, evaluation_id)[0].finding
    approver = world.acme_as("approver")
    resp = approver.post(
        f"/v1/findings/{finding.id}/resolutions",
        json={"resolution_code": "OVERRIDE", "reason": "please"},
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "FINDING_NOT_RESOLVABLE"


def test_fabricated_evidence_references_are_not_cited(world, db, acme_operator):
    from backend.domain.outcomes import RuleResult
    from backend.policies.engine import RuleOutput, rule

    @rule("test.cites", version=1, module="*", title="Cites")
    def _cites(inputs, params):
        return RuleOutput(RuleResult.FAIL, "C", "c", evidence_refs=tuple(inputs["refs"]))

    _publish(
        world,
        {
            **DOC,
            "rules": [{"code": "test.cites", "version": 1, "on_fail": "REVIEW"}],
            "scenarios": [],
        },
    )
    with db.tenant(world.acme, actor=acme_operator) as tx:
        real = record_evidence(tx, source_type="user", source_ref="note", locator={})
        globex_like = uuid.uuid4()
        tx.flush()
    _, evaluation_id = _evaluated_case(
        db, world, acme_operator, {"refs": [str(real.id), str(globex_like), "made-up"]}
    )
    with db.tenant(world.acme) as tx:
        view = policies.findings_for(tx, evaluation_id)[0]
    assert view.evidence_ids == [real.id]


def test_policies_are_tenant_isolated(world):
    published = _publish(world)
    assert world.globex_as("operator").get(f"/v1/policies/{published['id']}").status_code == 404
    codes = {p["policy_code"] for p in world.globex_as("operator").get("/v1/policies").json()}
    assert codes == {"invoice-preflight"}  # only Globex's own template


def test_no_active_policy_is_a_conflict(db, world):
    with db.tenant(world.acme) as tx, pytest.raises(Conflict):
        policies.active_policy(tx, "missing-policy")


def test_finding_rows_are_append_only(world, db, acme_operator):
    from sqlalchemy import update
    from sqlalchemy.exc import DBAPIError

    _publish(world)
    _, evaluation_id = _evaluated_case(db, world, acme_operator, {"a": 1, "b": 2})
    with pytest.raises(DBAPIError), db.tenant(world.acme) as tx:
        tx.session.execute(
            update(Finding).where(Finding.evaluation_id == evaluation_id).values(effect=None)
        )
