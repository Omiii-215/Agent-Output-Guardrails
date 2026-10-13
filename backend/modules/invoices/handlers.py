"""Invoice job handlers and the invoice section of case detail."""

from __future__ import annotations

from typing import Any

from backend.ai import explanations
from backend.cases import detail
from backend.cases.models import Case, CaseStatus
from backend.domain.money import Money
from backend.evidence.models import EvidenceItem
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.worker import JobContext, registry

from . import service
from .models import BeneficiaryVersion, Invoice, Vendor


@registry.handler(service.EVALUATE_JOB)
def evaluate(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        service.evaluate_case(tx, ctx.job.object_ref, created_by=ctx.actor.subject)


def _money(minor: int | None, currency: str | None) -> dict[str, str] | None:
    if minor is None or not currency:
        return None
    m = Money(minor, currency)
    return {**m.to_api(), "formatted": m.format()}


def next_actions(tx: TenantSession, case: Case) -> list[str]:
    if case.status == CaseStatus.NEEDS_INFORMATION:
        return ["CORRECT_FIELDS"]
    if case.status == CaseStatus.READY_TO_EVALUATE:
        return ["RUN_EVALUATION", "CORRECT_FIELDS"]
    if case.status != CaseStatus.IN_REVIEW:
        return []
    evaluation = policies.latest_evaluation(tx, case.id, "DOCUMENT")
    if evaluation is None:
        return ["RUN_EVALUATION"]
    views = policies.findings_for(tx, evaluation.id)
    actions: list[str] = []
    reasons = {v.finding.reason_code for v in views if v.finding.effect}
    if evaluation.outcome == "BLOCK":
        actions += ["CORRECT_SOURCE", "CLOSE_CASE"]
    elif evaluation.outcome == "INDETERMINATE":
        if "BENEFICIARY_VERIFICATION_MISSING" in reasons:
            actions.append("REQUEST_BENEFICIARY_VERIFICATION")
        actions.append("PROVIDE_EVIDENCE")
    elif any(v.finding.effect == "REVIEW" and not v.resolved for v in views):
        actions.append("RESOLVE_FINDINGS")
    else:
        actions.append("CREATE_PAYMENT_PROPOSAL")
    return actions


def invoice_section(tx: TenantSession, case: Case) -> detail.DetailSection:
    invoice = tx.first(tx.select(Invoice).where(Invoice.case_id == case.id))
    if invoice is None:
        return detail.DetailSection()
    version = service.current_version(tx, invoice)
    vendor = tx.get(Vendor, invoice.vendor_id)
    # The payee is the vendor's current version; evaluations freeze which one they saw.
    ben = (
        tx.find(BeneficiaryVersion, vendor.current_beneficiary_id)
        if vendor.current_beneficiary_id
        else None
    )
    evaluation = policies.latest_evaluation(tx, case.id, "DOCUMENT")
    findings: list[dict[str, Any]] = []
    evidence: dict[str, Any] = {}
    if evaluation is not None:
        for view in policies.findings_for(tx, evaluation.id):
            f = view.finding
            findings.append(
                {
                    "id": f.id,
                    "rule_code": f.rule_code,
                    "title": f.title,
                    "result": f.result,
                    "effect": f.effect,
                    "severity": f.severity,
                    "reason_code": f.reason_code,
                    "message": f.message,
                    "observed": f.observed,
                    "expected": f.expected,
                    "evidence_ids": view.evidence_ids,
                    "resolutions": [
                        {
                            "resolution_code": r.resolution_code,
                            "reason": r.reason,
                            "actor_subject": r.actor_subject,
                            "created_at": r.created_at,
                        }
                        for r in view.resolutions
                    ],
                }
            )
            for eid in view.evidence_ids:
                item = tx.get(EvidenceItem, eid)
                evidence[str(eid)] = {
                    "source_type": item.source_type,
                    "locator": item.locator,
                    "excerpt": item.excerpt,
                    "document_version_id": item.document_version_id,
                }
    cur = version.currency
    data = {
        "invoice": {
            "id": invoice.id,
            "version": version.version,
            "document_version_id": invoice.document_version_id,
            "source": version.source,
            "number": version.number_raw,
            "invoice_date": version.invoice_date,
            "due_date": version.due_date,
            "currency": cur,
            "subtotal": _money(version.subtotal_minor, cur),
            "tax": _money(version.tax_minor, cur),
            "total": _money(version.total_minor, cur),
            "po_number": version.po_number,
            "lines": version.lines,
            "field_status": version.field_status,
        },
        "vendor": {"id": vendor.id, "name": vendor.name, "tax_id": vendor.tax_id},
        "beneficiary": (
            {
                "id": ben.id,
                "revision": ben.revision,
                "account_holder": ben.account_holder,
                "account_masked": "•••• " + ben.account_last4,
                "ifsc": ben.ifsc,
                "verification_status": ben.verification_status,
                "verified_by": ben.verified_by,
            }
            if ben
            else None
        ),
        "evaluation": (
            {
                "id": evaluation.id,
                "outcome": evaluation.outcome,
                "policy_version_id": evaluation.policy_version_id,
                "input_digest": evaluation.input_digest,
                "engine_version": evaluation.engine_version,
                "coverage": evaluation.coverage,
                "explanation": (
                    explanation.summary
                    if (explanation := explanations.latest_for(tx, evaluation.id))
                    else None
                ),
                "created_at": evaluation.created_at,
            }
            if evaluation
            else None
        ),
        "findings": findings,
        "evidence": evidence,
        "next_actions": next_actions(tx, case),
    }
    return detail.DetailSection(data=data, related_ids=[invoice.id, vendor.id])


detail.register("invoices", invoice_section)
