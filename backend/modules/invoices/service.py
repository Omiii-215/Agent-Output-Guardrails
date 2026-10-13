"""Invoice preflight workflow: vendors, payees, invoices, corrections, evaluation."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, select

from backend.adapters.crypto import FieldCipher
from backend.cases import hooks
from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.domain.clock import utcnow
from backend.domain.money import Money, MoneyError, exponent_for, to_decimal
from backend.errors import Conflict, Forbidden, InvalidInput
from backend.evidence.service import require_clean
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.telemetry import audit

from .models import BeneficiaryVersion, Invoice, InvoiceVersion, PaymentRecord, Vendor

POLICY_CODE = "invoice-preflight"
EVALUATE_JOB = "invoices.evaluate"
CRITICAL_FIELDS = ("vendor", "invoice_number", "currency", "total")
FIELD_NAMES = (
    "invoice_number",
    "invoice_date",
    "due_date",
    "currency",
    "subtotal",
    "tax",
    "total",
    "po_number",
)
SIMILAR_WINDOW_DAYS = 7

_LEGAL_SUFFIXES = re.compile(r"\b(private|pvt|limited|ltd|llp|inc|co|company)\b")
_IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")


def normalize_vendor_name(name: str) -> str:
    text = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    text = _LEGAL_SUFFIXES.sub(" ", text)
    return " ".join(text.split())


def normalize_invoice_number(raw: str | None) -> str | None:
    """Matching aid only: uppercase alphanumerics. Not proof of identity."""
    if not raw:
        return None
    return re.sub(r"[^A-Z0-9]", "", raw.upper()) or None


# -- vendors and beneficiaries ------------------------------------------------


def create_vendor(tx: TenantSession, actor: Actor, *, name: str, tax_id: str | None) -> Vendor:
    actor.require(Capability.VENDOR_WRITE)
    normalized = normalize_vendor_name(name)
    if tx.first(tx.select(Vendor).where(Vendor.normalized_name == normalized)):
        raise Conflict("A vendor with this name already exists", code="VENDOR_EXISTS")
    vendor = tx.add(
        Vendor(name=name, normalized_name=normalized, tax_id=tax_id, created_by=actor.subject)
    )
    tx.flush()
    audit.record(tx, "vendor.created", object_type="vendor", object_id=vendor.id)
    return vendor


def add_beneficiary(
    tx: TenantSession,
    actor: Actor,
    cipher: FieldCipher,
    vendor_id: uuid.UUID,
    *,
    account_holder: str,
    account_number: str,
    ifsc: str,
) -> BeneficiaryVersion:
    """Record new bank details. They stay UNVERIFIED until independently verified."""
    actor.require(Capability.VENDOR_WRITE)
    account_number = re.sub(r"\s", "", account_number)
    if not account_number.isdigit() or not 6 <= len(account_number) <= 20:
        raise InvalidInput("Account number must be 6-20 digits", code="ACCOUNT_NUMBER")
    ifsc = ifsc.upper().strip()
    if not _IFSC.match(ifsc):
        raise InvalidInput("IFSC must look like ABCD0123456", code="IFSC")
    vendor = tx.get(Vendor, vendor_id, for_update=True)
    previous = (
        tx.find(BeneficiaryVersion, vendor.current_beneficiary_id)
        if vendor.current_beneficiary_id
        else None
    )
    revision = (previous.revision + 1) if previous else 1
    version = tx.add(
        BeneficiaryVersion(
            vendor_id=vendor.id,
            revision=revision,
            account_holder=account_holder,
            account_ciphertext=cipher.encrypt(account_number),
            account_fingerprint=cipher.fingerprint(account_number),
            account_last4=account_number[-4:],
            ifsc=ifsc,
            created_by=actor.subject,
        )
    )
    tx.flush()
    vendor.current_beneficiary_id = version.id
    audit.record(
        tx,
        "beneficiary.changed",
        object_type="vendor",
        object_id=vendor.id,
        data={
            "beneficiary_version_id": version.id,
            "revision": revision,
            "account_changed": bool(
                previous and previous.account_fingerprint != version.account_fingerprint
            ),
            "last4": version.account_last4,
        },
    )
    _mark_dependent_cases_stale(tx, vendor.id, "Beneficiary details changed")
    return version


def verify_beneficiary(
    tx: TenantSession,
    actor: Actor,
    beneficiary_version_id: uuid.UUID,
    *,
    decision: str,
    note: str,
) -> BeneficiaryVersion:
    actor.require(Capability.BENEFICIARY_VERIFY)
    version = tx.get(BeneficiaryVersion, beneficiary_version_id, for_update=True)
    if decision not in ("VERIFIED", "REJECTED"):
        raise InvalidInput("Decision must be VERIFIED or REJECTED")
    if version.created_by == actor.subject:
        raise Forbidden(
            "Bank details need verification by someone other than who entered them",
            code="SELF_VERIFICATION",
        )
    if version.verification_status != "UNVERIFIED":
        raise Conflict("This version was already decided", code="ALREADY_DECIDED")
    version.verification_status = decision
    version.verification_note = note
    version.verified_by = actor.subject
    version.verified_at = utcnow()
    audit.record(
        tx,
        f"beneficiary.{decision.lower()}",
        object_type="vendor",
        object_id=version.vendor_id,
        reason=note,
        data={"beneficiary_version_id": version.id, "revision": version.revision},
    )
    _mark_dependent_cases_stale(tx, version.vendor_id, f"Beneficiary {decision.lower()}")
    return version


def _mark_dependent_cases_stale(tx: TenantSession, vendor_id: uuid.UUID, reason: str) -> None:
    """Payee changes invalidate prior evaluations of open invoice cases for this vendor."""
    rows = tx.session.execute(
        tx.select(Case)
        .join(
            Invoice,
            and_(Invoice.case_id == Case.id, Invoice.organization_id == Case.organization_id),
        )
        .where(
            Invoice.vendor_id == vendor_id,
            Case.status.in_([CaseStatus.IN_REVIEW, CaseStatus.READY_FOR_ACTION]),
        )
    ).scalars()
    for case in rows:
        hooks.notify_inputs_changed(tx, case, reason)
        if case.status == CaseStatus.READY_FOR_ACTION:
            cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)
        cases.transition(tx, case, CaseStatus.READY_TO_EVALUATE, reason=reason)
        jobs.emit(tx, "case.inputs_changed", aggregate_id=case.id, aggregate_revision=case.revision)


def import_payment_history(
    tx: TenantSession, actor: Actor, records: list[dict[str, Any]]
) -> dict[str, int]:
    actor.require(Capability.RECON_IMPORT)
    created = skipped = 0
    for rec in records:
        tx.get(Vendor, rec["vendor_id"])
        exists = tx.first(
            tx.select(PaymentRecord).where(
                PaymentRecord.source == "IMPORT",
                PaymentRecord.external_reference == rec["external_reference"],
            )
        )
        if exists:
            skipped += 1
            continue
        money = Money.from_major(rec["amount"], rec["currency"])
        tx.add(
            PaymentRecord(
                vendor_id=rec["vendor_id"],
                number_normalized=normalize_invoice_number(rec["invoice_number"]) or "",
                currency=money.currency,
                amount_minor=money.minor,
                paid_on=rec["paid_on"],
                external_reference=rec["external_reference"],
                source="IMPORT",
            )
        )
        created += 1
    tx.flush()
    audit.record(
        tx,
        "payment_history.imported",
        object_type="organization",
        object_id=tx.organization_id,
        data={"created": created, "skipped": skipped},
    )
    return {"created": created, "skipped": skipped}


# -- invoices -----------------------------------------------------------------


@dataclass
class FieldInput:
    """Field values as entered (major-unit decimals as strings)."""

    values: dict[str, Any]
    lines: list[dict[str, Any]] | None


def parse_fields(
    values: dict[str, Any], currency_hint: str | None
) -> tuple[dict[str, Any], list[str]]:
    """Convert API field values into stored columns; return (columns, errors)."""
    out: dict[str, Any] = {}
    errors: list[str] = []
    unknown = set(values) - set(FIELD_NAMES)
    if unknown:
        errors.append(f"Unknown fields: {', '.join(sorted(unknown))}")
    currency = values.get("currency", currency_hint)
    if "currency" in values:
        try:
            exponent_for(values["currency"])
            out["currency"] = values["currency"]
        except MoneyError as exc:
            errors.append(str(exc))
    if "invoice_number" in values:
        out["number_raw"] = values["invoice_number"]
        out["number_normalized"] = normalize_invoice_number(values["invoice_number"])
    for key in ("invoice_date", "due_date"):
        if key in values:
            try:
                out[key] = date.fromisoformat(values[key]) if values[key] else None
            except (TypeError, ValueError):
                errors.append(f"{key} must be an ISO date")
    if "po_number" in values:
        out["po_number"] = values["po_number"] or None
    for key in ("subtotal", "tax", "total"):
        if key in values:
            if values[key] in (None, ""):
                out[f"{key}_minor"] = None
                continue
            if not currency:
                errors.append(f"{key} needs a currency")
                continue
            try:
                out[f"{key}_minor"] = Money.from_major(values[key], currency).minor
            except MoneyError as exc:
                errors.append(f"{key}: {exc}")
    return out, errors


def parse_lines(lines: list[dict[str, Any]]) -> list[dict[str, str]]:
    parsed = []
    for i, line in enumerate(lines, start=1):
        try:
            parsed.append(
                {
                    "line_no": str(i),
                    "description": str(line.get("description", ""))[:300],
                    "quantity": str(to_decimal(line["quantity"])),
                    "unit_price": str(to_decimal(line["unit_price"])),
                    "tax_rate": str(to_decimal(line.get("tax_rate", "0"))),
                }
            )
        except (KeyError, MoneyError) as exc:
            raise InvalidInput(f"Line {i} is invalid: {exc}", code="INVALID_LINE") from None
    return parsed


def field_value(version: InvoiceVersion, name: str) -> Any:
    mapping = {
        "vendor": version.vendor_id,
        "invoice_number": version.number_raw,
        "invoice_date": version.invoice_date,
        "due_date": version.due_date,
        "currency": version.currency,
        "subtotal": version.subtotal_minor,
        "tax": version.tax_minor,
        "total": version.total_minor,
        "po_number": version.po_number,
    }
    return mapping[name]


def _critical_complete(version: InvoiceVersion) -> bool:
    """Critical fields are present and none is an unconfirmed machine extraction."""
    return all(
        field_value(version, f) not in (None, "")
        and version.field_status.get(f, {}).get("status") != "EXTRACTED"
        for f in CRITICAL_FIELDS
    )


def create_invoice(
    tx: TenantSession,
    actor: Actor,
    *,
    vendor_id: uuid.UUID,
    document_version_id: uuid.UUID | None,
    fields: FieldInput,
    extract: bool = False,
) -> tuple[Case, Invoice]:
    actor.require(Capability.CASE_WRITE)
    vendor = tx.get(Vendor, vendor_id)
    if document_version_id is not None:
        require_clean(tx, document_version_id)
        if tx.first(tx.select(Invoice).where(Invoice.document_version_id == document_version_id)):
            raise Conflict("This document already has an invoice case", code="DOCUMENT_IN_USE")
    columns, errors = parse_fields(fields.values, None)
    if errors:
        raise InvalidInput("Invoice fields are invalid", code="INVALID_FIELDS", details=errors)

    number = fields.values.get("invoice_number")
    case = cases.create_case(
        tx,
        actor,
        module="invoices",
        title=f"{vendor.name} · {number or 'invoice'}",
        subject_type="invoice",
    )
    invoice = tx.add(
        Invoice(case_id=case.id, vendor_id=vendor.id, document_version_id=document_version_id)
    )
    tx.flush()
    case.subject_id = invoice.id

    status = {name: {"status": "ENTERED", "evidence_refs": []} for name in fields.values}
    status["vendor"] = {"status": "ENTERED", "evidence_refs": []}
    version = tx.add(
        InvoiceVersion(
            invoice_id=invoice.id,
            version=1,
            vendor_id=vendor.id,
            beneficiary_version_id=vendor.current_beneficiary_id,
            lines=parse_lines(fields.lines or []),
            field_status=status,
            source="MANUAL",
            created_by=actor.subject,
            **columns,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "invoice.created",
        object_type="case",
        object_id=case.id,
        data={"invoice_id": invoice.id, "version": 1, "document_version_id": document_version_id},
    )
    if extract and document_version_id is not None:
        cases.transition(tx, case, CaseStatus.EXTRACTING)
        jobs.enqueue(
            tx,
            "invoices.extract",
            object_ref=invoice.id,
            dedupe_key=f"{invoice.id}:extract:{document_version_id}",
        )
    elif _critical_complete(version):
        cases.transition(tx, case, CaseStatus.READY_TO_EVALUATE)
    else:
        cases.transition(tx, case, CaseStatus.NEEDS_INFORMATION, reason="Critical fields missing")
    return case, invoice


def current_version(tx: TenantSession, invoice: Invoice) -> InvoiceVersion:
    version = tx.first(
        tx.select(InvoiceVersion).where(
            InvoiceVersion.invoice_id == invoice.id,
            InvoiceVersion.version == invoice.current_version,
        )
    )
    assert version is not None
    return version


def new_version(
    tx: TenantSession,
    invoice: Invoice,
    *,
    columns: dict[str, Any],
    lines: list[dict[str, str]] | None,
    field_status: dict[str, Any],
    source: str,
    reason: str | None,
    created_by: str,
    extraction_meta: dict[str, Any] | None = None,
) -> InvoiceVersion:
    base = current_version(tx, invoice)
    vendor = tx.get(Vendor, invoice.vendor_id)
    data = {
        "vendor_id": base.vendor_id,
        "beneficiary_version_id": vendor.current_beneficiary_id,
        "number_raw": base.number_raw,
        "number_normalized": base.number_normalized,
        "invoice_date": base.invoice_date,
        "due_date": base.due_date,
        "currency": base.currency,
        "subtotal_minor": base.subtotal_minor,
        "tax_minor": base.tax_minor,
        "total_minor": base.total_minor,
        "po_number": base.po_number,
        **columns,
    }
    version = tx.add(
        InvoiceVersion(
            invoice_id=invoice.id,
            version=invoice.current_version + 1,
            lines=lines if lines is not None else list(base.lines),
            field_status=field_status,
            source=source,
            reason=reason,
            created_by=created_by,
            extraction_meta=(
                extraction_meta if extraction_meta is not None else dict(base.extraction_meta)
            ),
            **data,
        )
    )
    invoice.current_version += 1
    tx.flush()
    return version


def correct_invoice(
    tx: TenantSession,
    actor: Actor,
    invoice_id: uuid.UUID,
    *,
    expected_revision: int,
    fields: FieldInput,
    verify: list[str],
    reason: str,
) -> InvoiceVersion:
    """Correct or confirm fields. Creates a new version; never overwrites history."""
    actor.require(Capability.CASE_WRITE)
    invoice = tx.get(Invoice, invoice_id, for_update=True)
    case = cases.get_for_update(tx, invoice.case_id)
    cases.check_revision(case, expected_revision)
    if case.status in cases.TERMINAL or case.status in (
        CaseStatus.ACTION_PENDING,
        CaseStatus.EVALUATING,
    ):
        raise Conflict(f"Invoice cannot be corrected while {case.status}", code="CASE_LOCKED")
    base = current_version(tx, invoice)
    columns, errors = parse_fields(fields.values, base.currency)
    bad_verify = set(verify) - set(FIELD_NAMES) - {"vendor"}
    if bad_verify:
        errors.append(f"Unknown fields to verify: {', '.join(sorted(bad_verify))}")
    if errors:
        raise InvalidInput("Invoice fields are invalid", code="INVALID_FIELDS", details=errors)

    status = {k: dict(v) for k, v in base.field_status.items()}
    for name in fields.values:
        status[name] = {"status": "ENTERED", "evidence_refs": []}
    for name in verify:
        entry = status.setdefault(name, {"evidence_refs": []})
        entry["status"] = "VERIFIED"
        entry["verified_by"] = actor.subject
    version = new_version(
        tx,
        invoice,
        columns=columns,
        lines=parse_lines(fields.lines) if fields.lines is not None else None,
        field_status=status,
        source="CORRECTION",
        reason=reason,
        created_by=actor.subject,
    )
    audit.record(
        tx,
        "invoice.corrected",
        object_type="case",
        object_id=case.id,
        reason=reason,
        data={
            "invoice_id": invoice.id,
            "version": version.version,
            "changed": sorted(fields.values),
            "verified": sorted(verify),
        },
    )
    _after_input_change(tx, case, version, reason)
    return version


def _after_input_change(
    tx: TenantSession, case: Case, version: InvoiceVersion, reason: str
) -> None:
    hooks.notify_inputs_changed(tx, case, reason)
    if case.status == CaseStatus.READY_FOR_ACTION:
        cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)
    target = (
        CaseStatus.READY_TO_EVALUATE
        if _critical_complete(version)
        else CaseStatus.NEEDS_INFORMATION
    )
    if case.status != target:
        cases.transition(tx, case, target, reason=reason)
    else:
        cases.touch(case)
    jobs.emit(tx, "case.inputs_changed", aggregate_id=case.id, aggregate_revision=case.revision)


def request_evaluation(
    tx: TenantSession, actor: Actor, case_id: uuid.UUID, expected_revision: int
) -> jobs.Job:
    actor.require(Capability.EVALUATION_RUN)
    case = cases.get_for_update(tx, case_id)
    if case.module != "invoices":
        raise InvalidInput("Not an invoice case", code="WRONG_MODULE")
    cases.check_revision(case, expected_revision)
    if case.status != CaseStatus.READY_TO_EVALUATE:
        raise Conflict(
            f"Case is {case.status}; provide required fields first",
            code="NOT_READY_TO_EVALUATE",
        )
    cases.transition(tx, case, CaseStatus.EVALUATING)
    return jobs.enqueue(
        tx, EVALUATE_JOB, object_ref=case.id, dedupe_key=f"{case.id}:{case.revision}"
    )


# -- snapshot -----------------------------------------------------------------


def build_inputs(tx: TenantSession, invoice: Invoice) -> tuple[dict[str, Any], dict[str, Any]]:
    """Gather the exact facts the rules see, plus the source revisions they came from."""
    version = current_version(tx, invoice)
    vendor = tx.get(Vendor, invoice.vendor_id)
    beneficiary = (
        tx.find(BeneficiaryVersion, vendor.current_beneficiary_id)
        if vendor.current_beneficiary_id
        else None
    )
    policy_doc = policies.document_of(policies.active_policy(tx, POLICY_CODE))

    fields: dict[str, Any] = {}
    for name in ("vendor", *FIELD_NAMES):
        entry = version.field_status.get(name, {})
        value = field_value(version, name)
        fields[name] = {
            "value": None if value is None else str(value),
            "status": entry.get("status", "MISSING"),
            "evidence_refs": entry.get("evidence_refs", []),
        }

    duplicates = _duplicates(tx, invoice, version)
    inputs = {
        "fields": fields,
        "rounding": policy_doc.rounding,
        "invoice": {
            "invoice_id": invoice.id,
            "version": version.version,
            "number_normalized": version.number_normalized,
            "currency": version.currency,
            "subtotal_minor": version.subtotal_minor,
            "tax_minor": version.tax_minor,
            "total_minor": version.total_minor,
            "po_number": version.po_number,
            "invoice_date": version.invoice_date,
            "lines": [
                {k: line[k] for k in ("quantity", "unit_price", "tax_rate")}
                for line in version.lines
            ],
        },
        "vendor": {"vendor_id": vendor.id, "name": vendor.name},
        "beneficiary": (
            {
                "beneficiary_version_id": beneficiary.id,
                "revision": beneficiary.revision,
                "verification_status": beneficiary.verification_status,
                "account_fingerprint": beneficiary.account_fingerprint,
                "changed_recently": beneficiary.revision > 1,
            }
            if beneficiary
            else None
        ),
        "duplicates": duplicates,
        "document": (
            {
                "document_version_id": invoice.document_version_id,
                "injection_flags": version.extraction_meta.get("injection_flags", []),
                "extraction_warnings": version.extraction_meta.get("warnings", []),
            }
            if invoice.document_version_id
            else None
        ),
    }
    revisions = {
        "invoice_id": invoice.id,
        "invoice_version": version.version,
        "vendor_id": vendor.id,
        "beneficiary_version_id": beneficiary.id if beneficiary else None,
        "beneficiary_status": beneficiary.verification_status if beneficiary else None,
    }
    return inputs, revisions


def _duplicates(tx: TenantSession, invoice: Invoice, version: InvoiceVersion) -> dict[str, Any]:
    paid, open_, similar = [], [], []
    if version.number_normalized and version.currency:
        for p in tx.scalars(
            tx.select(PaymentRecord).where(
                PaymentRecord.vendor_id == invoice.vendor_id,
                PaymentRecord.number_normalized == version.number_normalized,
                PaymentRecord.currency == version.currency,
            )
        ):
            paid.append(
                {
                    "payment_id": p.id,
                    "external_reference": p.external_reference,
                    "amount_minor": p.amount_minor,
                    "paid_on": p.paid_on,
                    "source": p.source,
                }
            )
    others = tx.session.execute(
        select(InvoiceVersion, Invoice)
        .join(
            Invoice,
            and_(
                Invoice.id == InvoiceVersion.invoice_id,
                Invoice.organization_id == InvoiceVersion.organization_id,
                Invoice.current_version == InvoiceVersion.version,
            ),
        )
        .where(
            InvoiceVersion.organization_id == tx.organization_id,
            Invoice.vendor_id == invoice.vendor_id,
            Invoice.id != invoice.id,
        )
    ).all()
    for other, other_invoice in others:
        ref = {"invoice_id": other_invoice.id, "case_id": other_invoice.case_id}
        if (
            version.number_normalized
            and other.number_normalized == version.number_normalized
            and other.currency == version.currency
        ):
            open_.append(ref)
        elif (
            version.total_minor is not None
            and other.total_minor == version.total_minor
            and other.currency == version.currency
            and version.invoice_date
            and other.invoice_date
            and abs(other.invoice_date - version.invoice_date)
            <= timedelta(days=SIMILAR_WINDOW_DAYS)
        ):
            similar.append({**ref, "number": other.number_raw})
    return {"paid": paid, "open": open_, "similar": similar}


def evaluate_case(tx: TenantSession, case_id: uuid.UUID, created_by: str) -> None:
    """Job body: freeze inputs, evaluate the active policy, move the case to review."""
    case = cases.get_for_update(tx, case_id)
    if case.status != CaseStatus.EVALUATING:
        return  # duplicate delivery or superseded request
    invoice = tx.first(tx.select(Invoice).where(Invoice.case_id == case.id))
    assert invoice is not None
    inputs, revisions = build_inputs(tx, invoice)
    policy = policies.active_policy(tx, POLICY_CODE)
    evaluation = policies.record_evaluation(
        tx,
        case=case,
        kind="DOCUMENT",
        inputs=inputs,
        source_revision_map=revisions,
        policy=policy,
        created_by=created_by,
    )
    case.outcome = evaluation.outcome
    cases.transition(
        tx,
        case,
        CaseStatus.IN_REVIEW,
        data={"evaluation_id": evaluation.id, "outcome": evaluation.outcome},
    )
