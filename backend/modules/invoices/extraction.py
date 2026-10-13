"""Invoice extraction job.

Three steps so no model call happens inside a database transaction:
1. load references in a short transaction;
2. read the verified bytes, extract text and call the AI gateway;
3. record evidence and a new EXTRACTED invoice version in a fenced transaction.

Extracted values never overwrite what a person entered, and they always need
confirmation before evaluation. If AI is unavailable after retries the case
moves to NEEDS_INFORMATION for manual entry instead of silently waiting.
"""

from __future__ import annotations

import uuid

from backend.adapters.models.base import ModelUnavailable
from backend.adapters.ocr.text import extract_text
from backend.ai import gateway
from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.evidence.service import record_evidence, require_clean
from backend.persistence.database import TenantSession
from backend.persistence.jobs import RetryableError
from backend.telemetry import audit
from backend.worker import JobContext, registry

from . import service
from .models import Invoice, Vendor

EXTRACT_JOB = "invoices.extract"


@registry.handler(EXTRACT_JOB)
def extract(ctx: JobContext) -> None:
    rt = ctx.runtime
    org = ctx.job.organization_id
    with rt.db.tenant(org) as tx:
        invoice = tx.get(Invoice, ctx.job.object_ref)
        case = tx.get(Case, invoice.case_id)
        if case.status != CaseStatus.EXTRACTING or invoice.document_version_id is None:
            return
        doc = require_clean(tx, invoice.document_version_id)
        object_key, media_type, doc_id = doc.object_key, doc.media_type, doc.id

    text = extract_text(rt.objects.get(org, object_key), media_type)
    outcome, failure = None, None
    if text.status != "OK":
        failure = f"TEXT_{text.status}"
    else:
        try:
            outcome = gateway.extract_invoice(
                rt.models,
                [(p.page, p.text) for p in text.pages],
                max_chars=rt.settings.model_max_input_chars,
            )
        except ModelUnavailable as exc:
            if ctx.job.attempts < ctx.job.max_attempts:
                raise RetryableError(str(exc), code="MODEL_UNAVAILABLE") from exc
            failure = "EXTRACTION_UNAVAILABLE"

    with ctx.fenced() as tx:
        apply(tx, invoice.id, doc_id, outcome, failure, extractor=text.extractor)


def apply(
    tx: TenantSession,
    invoice_id: uuid.UUID,
    document_version_id: uuid.UUID,
    outcome: gateway.ExtractionOutcome | None,
    failure: str | None,
    *,
    extractor: str,
) -> None:
    invoice = tx.get(Invoice, invoice_id, for_update=True)
    case = cases.get_for_update(tx, invoice.case_id)
    if case.status != CaseStatus.EXTRACTING:
        return
    if failure or outcome is None:
        audit.record(
            tx, "invoice.extraction_failed", object_type="case", object_id=case.id, reason=failure
        )
        cases.transition(
            tx, case, CaseStatus.NEEDS_INFORMATION, reason=f"{failure}: enter fields manually"
        )
        return

    base = service.current_version(tx, invoice)
    status = {k: dict(v) for k, v in base.field_status.items()}
    values: dict[str, str] = {}
    warnings = list(outcome.warnings)
    vendor = tx.get(Vendor, invoice.vendor_id)

    for f in outcome.fields:
        item = record_evidence(
            tx,
            source_type="document",
            source_ref=f"{document_version_id}#p{f.page}:{f.start}-{f.end}",
            document_version_id=document_version_id,
            locator={"kind": "text_span", "page": f.page, "start": f.start, "end": f.end},
            excerpt=f.excerpt,
        )
        if f.name == "vendor_name":
            if service.normalize_vendor_name(f.value) != vendor.normalized_name:
                warnings.append("VENDOR_NAME_MISMATCH")
            status["vendor"] = {
                **status.get("vendor", {}),
                "evidence_refs": [str(item.id)],
            }
            continue
        existing = status.get(f.name)
        if existing and existing.get("status") in ("ENTERED", "VERIFIED"):
            current = service.field_value(base, f.name)
            if current is not None and str(current) != _comparable(f.name, f.value, base.currency):
                warnings.append(f"CONFLICT:{f.name}")
            existing.setdefault("evidence_refs", []).append(str(item.id))
            continue
        values[f.name] = f.value
        status[f.name] = {
            "status": "EXTRACTED",
            "evidence_refs": [str(item.id)],
            "model_version": outcome.model_version,
        }

    lines = None
    if outcome.lines and not base.lines:
        lines = []
        for line in outcome.lines:
            record_evidence(
                tx,
                source_type="document",
                source_ref=f"{document_version_id}#p{line.page}:{line.start}-{line.end}",
                document_version_id=document_version_id,
                locator={
                    "kind": "text_span",
                    "page": line.page,
                    "start": line.start,
                    "end": line.end,
                },
                excerpt=line.excerpt,
            )
            lines.append(
                {
                    "description": line.description,
                    "quantity": line.quantity,
                    "unit_price": line.unit_price,
                    "tax_rate": line.tax_rate,
                }
            )
        status["lines"] = {"status": "EXTRACTED", "evidence_refs": []}

    columns, errors = service.parse_fields(values, base.currency)
    warnings += [f"VALUE_INVALID:{e}" for e in errors]
    version = service.new_version(
        tx,
        invoice,
        columns={} if errors else columns,
        lines=service.parse_lines(lines) if lines is not None else None,
        field_status=status,
        source="EXTRACTED",
        reason="Automated extraction; requires confirmation",
        created_by="system:extraction",
        extraction_meta={
            "extractor": extractor,
            "model_version": outcome.model_version,
            "warnings": warnings,
            "injection_flags": outcome.injection_flags,
            "truncated": outcome.truncated,
        },
    )
    audit.record(
        tx,
        "invoice.extracted",
        object_type="case",
        object_id=case.id,
        data={
            "invoice_version": version.version,
            "fields": sorted(values),
            "warnings": warnings,
            "injection_flags": len(outcome.injection_flags),
            "model_version": outcome.model_version,
        },
    )
    cases.transition(
        tx, case, CaseStatus.NEEDS_INFORMATION, reason="Extracted fields need confirmation"
    )


def _comparable(name: str, value: str, currency: str | None) -> str:
    if name in ("subtotal", "tax", "total") and currency:
        from backend.domain.money import Money

        return str(Money.from_major(value, currency).minor)
    return value
