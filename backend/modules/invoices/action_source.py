"""Payment facts for invoice cases, consumed by the shared M5 gateway."""

from __future__ import annotations

from backend.actions import sources
from backend.actions.sources import PaymentFacts
from backend.cases.models import Case, CaseStatus
from backend.domain.money import Money
from backend.errors import Conflict
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.policies.models import InputSnapshot

from . import service
from .models import BeneficiaryVersion, Invoice, PaymentRecord, Vendor

_REVIEWED = (CaseStatus.IN_REVIEW, CaseStatus.READY_FOR_ACTION, CaseStatus.ACTION_PENDING)


def invoice_payment_facts(tx: TenantSession, case: Case) -> PaymentFacts:
    invoice = tx.first(tx.select(Invoice).where(Invoice.case_id == case.id))
    if invoice is None:
        raise Conflict("Case has no invoice", code="NO_INVOICE")
    version = service.current_version(tx, invoice)
    if version.total_minor is None or not version.currency:
        raise Conflict("Invoice has no confirmed total", code="NO_TOTAL")
    vendor = tx.get(Vendor, invoice.vendor_id)
    ben = (
        tx.find(BeneficiaryVersion, vendor.current_beneficiary_id)
        if vendor.current_beneficiary_id
        else None
    )
    evaluation = policies.latest_evaluation(tx, case.id, "DOCUMENT")
    doc_eval = None
    if evaluation is not None:
        snapshot = tx.get(InputSnapshot, evaluation.snapshot_id)
        seen = snapshot.source_revision_map
        current = (
            case.status in _REVIEWED
            and str(seen.get("invoice_version")) == str(version.version)
            and str(seen.get("beneficiary_version_id")) == str(ben.id if ben else None)
            and seen.get("beneficiary_status") == (ben.verification_status if ben else None)
        )
        doc_eval = {
            "evaluation_id": str(evaluation.id),
            "outcome": evaluation.outcome,
            "unresolved": len(policies.unresolved_blockers(tx, evaluation)),
            "current": current,
        }
    paid = tx.scalars(
        tx.select(PaymentRecord).where(
            PaymentRecord.vendor_id == vendor.id,
            PaymentRecord.number_normalized == (version.number_normalized or ""),
            PaymentRecord.currency == version.currency,
        )
    )
    return PaymentFacts(
        expected_amount=Money(version.total_minor, version.currency),
        vendor_id=vendor.id,
        beneficiary=(
            {
                "beneficiary_version_id": str(ben.id),
                "revision": ben.revision,
                "account_fingerprint": ben.account_fingerprint,
                "account_last4": ben.account_last4,
                "ifsc": ben.ifsc,
                "verification_status": ben.verification_status,
            }
            if ben
            else None
        ),
        subject={
            "invoice_id": str(invoice.id),
            "invoice_version": version.version,
            "number_normalized": version.number_normalized,
        },
        document_evaluation=doc_eval,
        source_revisions={
            "invoice_version": version.version,
            "beneficiary_version_id": str(ben.id) if ben else None,
            "beneficiary_status": ben.verification_status if ben else None,
            "document_evaluation_id": doc_eval["evaluation_id"] if doc_eval else None,
        },
        executed_references=[
            {"payment_id": str(p.id), "external_reference": p.external_reference} for p in paid
        ],
    )


sources.register("invoices", invoice_payment_facts)
