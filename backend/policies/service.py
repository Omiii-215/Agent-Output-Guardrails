"""Policy lifecycle, evaluation persistence and finding resolutions.

Lifecycle: DRAFT → VALIDATED → PUBLISHED → RETIRED. Authors and publishers
are separate people; publishing re-runs the regression scenarios and emits
``policy.published`` so pending actions are re-evaluated.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func

from backend.cases.models import Case
from backend.domain.canonical import canonical_json, digest
from backend.domain.clock import utcnow
from backend.errors import Conflict, Forbidden, InvalidInput, NotFound
from backend.evidence.models import EvidenceItem
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.policies import engine
from backend.policies.models import (
    Evaluation,
    Finding,
    FindingEvidence,
    FindingResolution,
    InputSnapshot,
    PolicyLifecycle,
    PolicyVersion,
)
from backend.policies.schema import PolicyDocument
from backend.telemetry import audit

TEMPLATE_AUTHOR = "system:template"


def parse_document(raw: dict[str, Any]) -> PolicyDocument:
    try:
        return PolicyDocument.model_validate(raw)
    except ValidationError as exc:
        raise InvalidInput(
            "Policy document is invalid",
            code="POLICY_INVALID",
            details=[
                {"loc": ".".join(str(p) for p in e["loc"]), "msg": e["msg"]} for e in exc.errors()
            ],
        ) from None


def document_of(policy: PolicyVersion) -> PolicyDocument:
    return PolicyDocument.model_validate(policy.document)


def _next_version(tx: TenantSession, policy_code: str) -> int:
    current = tx.session.scalar(
        tx.select(PolicyVersion)
        .with_only_columns(func.max(PolicyVersion.version))
        .where(PolicyVersion.policy_code == policy_code)
    )
    return (current or 0) + 1


def _stored(doc: PolicyDocument) -> dict[str, Any]:
    return json.loads(doc.model_dump_json())


def create_draft(tx: TenantSession, actor: Actor, raw: dict[str, Any]) -> PolicyVersion:
    actor.require(Capability.POLICY_AUTHOR)
    doc = parse_document(raw)
    policy = tx.add(
        PolicyVersion(
            policy_code=doc.policy_code,
            version=_next_version(tx, doc.policy_code),
            module=doc.module,
            document=_stored(doc),
            digest=digest(_stored(doc)),
            author_subject=actor.subject,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "policy.drafted",
        object_type="policy_version",
        object_id=policy.id,
        data={"policy_code": doc.policy_code, "version": policy.version},
    )
    return policy


def validate(tx: TenantSession, actor: Actor, policy_id: uuid.UUID) -> PolicyVersion:
    actor.require(Capability.POLICY_AUTHOR)
    policy = tx.get(PolicyVersion, policy_id, for_update=True)
    if policy.lifecycle != PolicyLifecycle.DRAFT:
        raise Conflict("Only drafts can be validated", code="POLICY_NOT_DRAFT")
    doc = document_of(policy)
    errors = engine.validate_document(doc) or engine.run_scenarios(doc)
    policy.validation_errors = errors
    if errors:
        raise InvalidInput("Policy failed validation", code="POLICY_INVALID", details=errors)
    policy.lifecycle = PolicyLifecycle.VALIDATED
    audit.record(tx, "policy.validated", object_type="policy_version", object_id=policy.id)
    return policy


def publish(tx: TenantSession, actor: Actor, policy_id: uuid.UUID, reason: str) -> PolicyVersion:
    actor.require(Capability.POLICY_PUBLISH)
    policy = tx.get(PolicyVersion, policy_id, for_update=True)
    if policy.lifecycle != PolicyLifecycle.VALIDATED:
        raise Conflict("Only validated policies can be published", code="POLICY_NOT_VALIDATED")
    if policy.author_subject == actor.subject:
        raise Forbidden("Policies need an independent publisher", code="SELF_PUBLISH")
    doc = document_of(policy)
    failures = engine.validate_document(doc) or engine.run_scenarios(doc)
    if failures:
        raise InvalidInput(
            "Regression scenarios failed", code="POLICY_REGRESSION", details=failures
        )
    _activate(tx, policy, actor.subject, reason)
    return policy


def _activate(tx: TenantSession, policy: PolicyVersion, publisher: str, reason: str) -> None:
    previous = tx.scalars(
        tx.select(PolicyVersion)
        .where(
            PolicyVersion.policy_code == policy.policy_code,
            PolicyVersion.lifecycle == PolicyLifecycle.PUBLISHED,
        )
        .with_for_update()
    )
    now = utcnow()
    for old in previous:
        old.lifecycle = PolicyLifecycle.RETIRED
        old.retired_at = now
    policy.lifecycle = PolicyLifecycle.PUBLISHED
    policy.publisher_subject = publisher
    policy.publish_reason = reason
    policy.published_at = now
    tx.flush()
    audit.record(
        tx,
        "policy.published",
        object_type="policy_version",
        object_id=policy.id,
        reason=reason,
        data={
            "policy_code": policy.policy_code,
            "version": policy.version,
            "digest": policy.digest,
        },
    )
    jobs.emit(
        tx,
        "policy.published",
        aggregate_id=policy.id,
        aggregate_revision=policy.version,
        data={"policy_code": policy.policy_code, "module": policy.module},
    )


def install_template(tx: TenantSession, raw: dict[str, Any]) -> PolicyVersion:
    """Install a product-supplied template as the active version (onboarding/seed)."""
    doc = parse_document(raw)
    errors = engine.validate_document(doc) or engine.run_scenarios(doc)
    if errors:
        raise InvalidInput("Template policy is invalid", code="POLICY_INVALID", details=errors)
    policy = tx.add(
        PolicyVersion(
            policy_code=doc.policy_code,
            version=_next_version(tx, doc.policy_code),
            module=doc.module,
            document=_stored(doc),
            digest=digest(_stored(doc)),
            author_subject=TEMPLATE_AUTHOR,
            lifecycle=PolicyLifecycle.VALIDATED,
        )
    )
    tx.flush()
    _activate(tx, policy, TEMPLATE_AUTHOR, "Product template installed")
    return policy


def active_policy(tx: TenantSession, policy_code: str) -> PolicyVersion:
    policy = tx.first(
        tx.select(PolicyVersion).where(
            PolicyVersion.policy_code == policy_code,
            PolicyVersion.lifecycle == PolicyLifecycle.PUBLISHED,
        )
    )
    if policy is None:
        raise Conflict(f"No published policy '{policy_code}'", code="NO_ACTIVE_POLICY")
    return policy


# -- evaluations ---------------------------------------------------------------


def freeze_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    """Canonical JSON form; rules always evaluate this form so replays match."""
    return json.loads(canonical_json(inputs))


def record_evaluation(
    tx: TenantSession,
    *,
    case: Case,
    kind: str,
    inputs: dict[str, Any],
    source_revision_map: dict[str, Any],
    policy: PolicyVersion,
    created_by: str,
    proposal_id: uuid.UUID | None = None,
) -> Evaluation:
    frozen = freeze_inputs(inputs)
    snapshot = tx.add(
        InputSnapshot(
            module=case.module,
            canonical_inputs=frozen,
            digest=digest(frozen),
            source_revision_map=freeze_inputs(source_revision_map),
        )
    )
    tx.flush()
    result = engine.evaluate(document_of(policy), frozen)
    evaluation = tx.add(
        Evaluation(
            case_id=case.id,
            proposal_id=proposal_id,
            kind=kind,
            snapshot_id=snapshot.id,
            input_digest=snapshot.digest,
            policy_version_id=policy.id,
            policy_digest=policy.digest,
            engine_version=engine.ENGINE_VERSION,
            case_revision=case.revision,
            outcome=result.outcome.value,
            coverage=result.coverage,
            created_by=created_by,
        )
    )
    tx.flush()
    for f in result.findings:
        finding = tx.add(
            Finding(
                evaluation_id=evaluation.id,
                rule_code=f.rule_code,
                rule_version=f.rule_version,
                title=f.title,
                result=f.result.value,
                effect=f.effect,
                severity=f.severity.value,
                reason_code=f.reason_code,
                message=f.message,
                observed=freeze_inputs(f.observed),
                expected=freeze_inputs(f.expected),
                requires_review=f.requires_review,
            )
        )
        tx.flush()
        for ref in _known_evidence(tx, f.evidence_refs):
            tx.add(FindingEvidence(finding_id=finding.id, evidence_item_id=ref))
    tx.flush()
    audit.record(
        tx,
        "evaluation.completed",
        object_type="case",
        object_id=case.id,
        data={
            "evaluation_id": evaluation.id,
            "kind": kind,
            "outcome": evaluation.outcome,
            "input_digest": evaluation.input_digest,
            "policy_version_id": policy.id,
            "policy_version": policy.version,
        },
    )
    jobs.emit(
        tx,
        "evaluation.completed",
        aggregate_id=case.id,
        aggregate_revision=case.revision,
        data={"evaluation_id": evaluation.id, "kind": kind},
    )
    return evaluation


def _known_evidence(tx: TenantSession, refs: tuple[str, ...]) -> list[uuid.UUID]:
    """Only evidence items that exist in this tenant can be cited."""
    ids: list[uuid.UUID] = []
    for ref in dict.fromkeys(refs):
        try:
            candidate = uuid.UUID(ref)
        except (ValueError, TypeError):
            continue
        if tx.find(EvidenceItem, candidate) is not None:
            ids.append(candidate)
    return ids


def replay(tx: TenantSession, evaluation_id: uuid.UUID) -> engine.EvaluationResult:
    """Re-run an evaluation from its frozen snapshot and policy version."""
    evaluation = tx.get(Evaluation, evaluation_id)
    snapshot = tx.get(InputSnapshot, evaluation.snapshot_id)
    policy = tx.get(PolicyVersion, evaluation.policy_version_id)
    return engine.evaluate(document_of(policy), snapshot.canonical_inputs)


def latest_evaluation(tx: TenantSession, case_id: uuid.UUID, kind: str) -> Evaluation | None:
    return tx.first(
        tx.select(Evaluation)
        .where(Evaluation.case_id == case_id, Evaluation.kind == kind)
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    )


@dataclass
class FindingView:
    finding: Finding
    evidence_ids: list[uuid.UUID]
    resolutions: list[FindingResolution]

    @property
    def resolved(self) -> bool:
        now = utcnow()
        return any(r.expires_at is None or r.expires_at > now for r in self.resolutions)


def findings_for(tx: TenantSession, evaluation_id: uuid.UUID) -> list[FindingView]:
    findings = tx.scalars(
        tx.select(Finding).where(Finding.evaluation_id == evaluation_id).order_by(Finding.rule_code)
    )
    ids = [f.id for f in findings]
    evidence = tx.scalars(tx.select(FindingEvidence).where(FindingEvidence.finding_id.in_(ids)))
    resolutions = tx.scalars(
        tx.select(FindingResolution)
        .where(FindingResolution.finding_id.in_(ids))
        .order_by(FindingResolution.created_at)
    )
    return [
        FindingView(
            f,
            [e.evidence_item_id for e in evidence if e.finding_id == f.id],
            [r for r in resolutions if r.finding_id == f.id],
        )
        for f in findings
    ]


def unresolved_blockers(tx: TenantSession, evaluation: Evaluation) -> list[Finding]:
    """Findings that stop action eligibility for this evaluation."""
    views = findings_for(tx, evaluation.id)
    blocking = [v.finding for v in views if v.finding.effect in ("BLOCK", "INDETERMINATE")]
    pending_review = [v.finding for v in views if v.finding.effect == "REVIEW" and not v.resolved]
    return blocking + pending_review


def resolve_finding(
    tx: TenantSession,
    actor: Actor,
    finding_id: uuid.UUID,
    *,
    resolution_code: str,
    reason: str,
) -> FindingResolution:
    actor.require(Capability.FINDING_RESOLVE)
    finding = tx.get(Finding, finding_id)
    if finding.effect != "REVIEW":
        raise Conflict(
            "Only review findings can be resolved; correct the source and re-evaluate",
            code="FINDING_NOT_RESOLVABLE",
        )
    evaluation = tx.get(Evaluation, finding.evaluation_id)
    latest = latest_evaluation(tx, evaluation.case_id, evaluation.kind)
    if latest is None or latest.id != evaluation.id:
        raise Conflict("A newer evaluation supersedes this finding", code="STALE_EVALUATION")
    case = tx.get(Case, evaluation.case_id)
    if case.created_by == actor.subject:
        raise Forbidden("Findings need an independent reviewer", code="SELF_RESOLUTION")
    resolution = tx.add(
        FindingResolution(
            finding_id=finding.id,
            actor_subject=actor.subject,
            resolution_code=resolution_code,
            reason=reason,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "finding.resolved",
        object_type="case",
        object_id=case.id,
        reason=reason,
        data={"finding_id": finding.id, "rule_code": finding.rule_code, "code": resolution_code},
    )
    return resolution


def get_policy(tx: TenantSession, policy_id: uuid.UUID) -> PolicyVersion:
    policy = tx.find(PolicyVersion, policy_id)
    if policy is None:
        raise NotFound("Policy not found")
    return policy
