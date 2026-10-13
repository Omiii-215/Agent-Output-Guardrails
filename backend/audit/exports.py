"""Audit evidence exports (story P-06).

An export reconstructs each selected case: its documents (hashes, not bytes),
every input version, evaluation snapshots and policy versions, findings and
resolutions, proposals, approvals, execution attempts and the audit trail.
Restricted values (bank account numbers, ciphertexts, keyed fingerprints) are
never exported. The bundle carries a canonical digest so a copy can be
checked later. Exports are produced by a job, scoped to a stated purpose and
downloadable only by authorised users until they expire.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.actions.models import ActionAttempt, ActionIntent, ActionProposal
from backend.adapters.object_store.store import object_key
from backend.approvals.models import ApprovalDecision, ApprovalRequest
from backend.cases.models import Case, CaseComment
from backend.domain.canonical import digest, to_jsonable
from backend.domain.clock import ensure_aware, utcnow
from backend.errors import Conflict, InvalidInput
from backend.evidence.models import DocumentVersion, EvidenceItem
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.modules.invoices.models import Invoice, InvoiceVersion
from backend.persistence import jobs
from backend.persistence.base import Base, TenantMixin, TimestampMixin
from backend.persistence.database import TenantSession
from backend.policies.models import (
    Evaluation,
    Finding,
    FindingEvidence,
    FindingResolution,
    InputSnapshot,
    PolicyVersion,
)
from backend.telemetry import audit
from backend.telemetry.audit import AuditEvent

EXPORT_JOB = "audit.export"
EXPORT_TTL = timedelta(hours=24)
MAX_CASES = 500

# Keys removed wherever they appear in exported records.
RESTRICTED_KEYS = frozenset(
    {"account_ciphertext", "account_fingerprint", "account_number", "credential_hash"}
)


class AuditExport(TenantMixin, TimestampMixin, Base):
    __tablename__ = "audit_export"

    purpose: Mapped[str] = mapped_column(String(500))
    scope: Mapped[dict[str, Any]]
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    object_key: Mapped[str | None] = mapped_column(String(300))
    bundle_digest: Mapped[str | None] = mapped_column(String(80))
    case_count: Mapped[int] = mapped_column(default=0)
    requested_by: Mapped[str] = mapped_column(String(200))
    expires_at: Mapped[datetime | None]


def request_export(
    tx: TenantSession,
    actor: Actor,
    *,
    purpose: str,
    case_ids: list[uuid.UUID] | None,
    from_date: datetime | None,
    to_date: datetime | None,
) -> AuditExport:
    actor.require(Capability.AUDIT_EXPORT)
    if not case_ids and not (from_date and to_date):
        raise InvalidInput("Choose case IDs or a date range", code="EXPORT_SCOPE")
    if case_ids and len(case_ids) > MAX_CASES:
        raise InvalidInput(f"At most {MAX_CASES} cases per export", code="EXPORT_SCOPE")
    for case_id in case_ids or []:
        tx.get(Case, case_id)  # 404 for unknown or other-tenant cases
    export = tx.add(
        AuditExport(
            purpose=purpose,
            scope=to_jsonable({"case_ids": case_ids or [], "from": from_date, "to": to_date}),
            requested_by=actor.subject,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "audit_export.requested",
        object_type="audit_export",
        object_id=export.id,
        reason=purpose,
        data=export.scope,
    )
    jobs.enqueue(tx, EXPORT_JOB, object_ref=export.id, dedupe_key=str(export.id))
    return export


def _row(obj: Any) -> dict[str, Any]:
    data = {c.key: getattr(obj, c.key) for c in obj.__table__.columns}
    return _scrub(to_jsonable(data))


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if k not in RESTRICTED_KEYS}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


def _all(tx: TenantSession, model: type, *conditions: Any) -> list[Any]:
    return list(tx.scalars(tx.select(model).where(*conditions)))


def case_bundle(tx: TenantSession, case: Case) -> dict[str, Any]:
    evaluations = _all(tx, Evaluation, Evaluation.case_id == case.id)
    findings = _all(tx, Finding, Finding.evaluation_id.in_([e.id for e in evaluations]))
    finding_ids = [f.id for f in findings]
    finding_evidence = _all(tx, FindingEvidence, FindingEvidence.finding_id.in_(finding_ids))
    evidence = _all(
        tx, EvidenceItem, EvidenceItem.id.in_([fe.evidence_item_id for fe in finding_evidence])
    )
    proposals = _all(tx, ActionProposal, ActionProposal.case_id == case.id)
    requests = _all(tx, ApprovalRequest, ApprovalRequest.proposal_id.in_([p.id for p in proposals]))
    intents = _all(tx, ActionIntent, ActionIntent.case_id == case.id)
    invoices = _all(tx, Invoice, Invoice.case_id == case.id)
    doc_ids = {i.document_version_id for i in invoices if i.document_version_id}
    doc_ids |= {e.document_version_id for e in evidence if e.document_version_id}
    related_ids = (
        [case.id]
        + [i.id for i in invoices]
        + [p.id for p in proposals]
        + [r.id for r in requests]
        + [i.id for i in intents]
    )
    return {
        "case": _row(case),
        "comments": [_row(c) for c in _all(tx, CaseComment, CaseComment.case_id == case.id)],
        "documents": [_row(d) for d in _all(tx, DocumentVersion, DocumentVersion.id.in_(doc_ids))],
        "invoice_versions": [
            _row(v)
            for v in _all(
                tx, InvoiceVersion, InvoiceVersion.invoice_id.in_([i.id for i in invoices])
            )
        ],
        "evaluations": [_row(e) for e in evaluations],
        "snapshots": [
            _row(s)
            for s in _all(
                tx, InputSnapshot, InputSnapshot.id.in_([e.snapshot_id for e in evaluations])
            )
        ],
        "policy_versions": [
            _row(p)
            for p in _all(
                tx,
                PolicyVersion,
                PolicyVersion.id.in_({e.policy_version_id for e in evaluations}),
            )
        ],
        "findings": [_row(f) for f in findings],
        "finding_evidence": [_row(fe) for fe in finding_evidence],
        "evidence_items": [_row(e) for e in evidence],
        "finding_resolutions": [
            _row(r)
            for r in _all(tx, FindingResolution, FindingResolution.finding_id.in_(finding_ids))
        ],
        "proposals": [_row(p) for p in proposals],
        "approval_requests": [_row(r) for r in requests],
        "approval_decisions": [
            _row(d)
            for d in _all(
                tx, ApprovalDecision, ApprovalDecision.request_id.in_([r.id for r in requests])
            )
        ],
        "intents": [_row(i) for i in intents],
        "attempts": [
            _row(a)
            for a in _all(tx, ActionAttempt, ActionAttempt.intent_id.in_([i.id for i in intents]))
        ],
        "audit_events": [
            _row(e)
            for e in tx.scalars(
                tx.select(AuditEvent)
                .where(AuditEvent.object_id.in_(related_ids))
                .order_by(AuditEvent.occurred_at, AuditEvent.id)
            )
        ],
    }


def build(tx: TenantSession, export_id: uuid.UUID) -> tuple[AuditExport, bytes] | None:
    export = tx.get(AuditExport, export_id, for_update=True)
    if export.state != "PENDING":
        return None
    scope = export.scope
    stmt = tx.select(Case)
    if scope.get("case_ids"):
        stmt = stmt.where(Case.id.in_([uuid.UUID(c) for c in scope["case_ids"]]))
    else:
        stmt = stmt.where(
            Case.created_at >= datetime.fromisoformat(scope["from"].replace("Z", "+00:00")),
            Case.created_at <= datetime.fromisoformat(scope["to"].replace("Z", "+00:00")),
        )
    case_rows = list(tx.scalars(stmt.order_by(Case.created_at).limit(MAX_CASES)))
    cases = [case_bundle(tx, c) for c in case_rows]
    body = {
        "format": "finguard-audit-export-v1",
        "export_id": str(export.id),
        "organization_id": str(tx.organization_id),
        "purpose": export.purpose,
        "requested_by": export.requested_by,
        "generated_at": utcnow().isoformat(),
        "restricted_fields_excluded": sorted(RESTRICTED_KEYS),
        "cases": cases,
    }
    bundle_digest = digest(body)
    content = json.dumps({**body, "bundle_digest": bundle_digest}, indent=2).encode()
    export.case_count = len(cases)
    export.bundle_digest = bundle_digest
    export.object_key = object_key(tx.organization_id, "exports", f"{export.id}.json")
    return export, content


def download(tx: TenantSession, actor: Actor, export_id: uuid.UUID) -> AuditExport:
    actor.require(Capability.AUDIT_EXPORT)
    export = tx.get(AuditExport, export_id)
    if export.state != "READY":
        raise Conflict(f"Export is {export.state}", code="EXPORT_NOT_READY")
    if export.expires_at and ensure_aware(export.expires_at) <= utcnow():
        raise Conflict("Export expired; request a new one", code="EXPORT_EXPIRED")
    audit.record(tx, "audit_export.downloaded", object_type="audit_export", object_id=export.id)
    return export
