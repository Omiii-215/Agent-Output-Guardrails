"""Reconciliation workflow (LLD §10).

* Imports are idempotent per (side, content hash); rows are unique per
  (side, external id) and keep their raw values and row lineage.
* Matching proposes exact one-to-one, full-amount matches only: same
  normalised reference, equal signed amount, same currency, both unallocated
  and exactly one candidate on each side.
* Conflicting candidates — ambiguous references, amount differences (fees,
  partial payments), currency differences (FX), split payments, missing
  references — are routed to an exception case. Rows with no counterpart yet
  stay UNMATCHED until a later import. Nothing is silently matched by similarity.
* Approving a match locks both rows and re-checks before allocating.
"""

from __future__ import annotations

import csv
import io
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.domain.canonical import digest
from backend.domain.clock import utcnow
from backend.domain.money import Money, MoneyError
from backend.errors import Conflict, InvalidInput
from backend.evidence.models import DocumentVersion
from backend.evidence.service import require_clean
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.telemetry import audit

from .models import (
    ImportBatch,
    MatchAllocation,
    MatchGroup,
    ReconciliationException,
    SourceTransaction,
)

IMPORT_JOB = "reconciliation.import"
MATCH_JOB = "reconciliation.match"
MAX_ROWS = 100_000
SIDES = ("BANK", "LEDGER")


class Mapping(BaseModel):
    """Which CSV columns hold which fields. Validated before any row is read."""

    model_config = ConfigDict(extra="forbid")

    external_id: str
    booked_on: str
    amount: str
    reference: str | None = None
    description: str | None = None
    currency: str | None = None
    default_currency: str = "INR"
    date_format: str = Field(default="%Y-%m-%d", max_length=20)
    # Some exports show outflows as positive "debit" values; flip them if needed.
    negate_amounts: bool = False


def normalize_reference(raw: str | None) -> str | None:
    if not raw:
        return None
    return re.sub(r"[^A-Z0-9]", "", raw.upper()) or None


# -- import -------------------------------------------------------------------------


def request_import(
    tx: TenantSession,
    actor: Actor,
    *,
    document_version_id: uuid.UUID,
    side: str,
    mapping: Mapping,
) -> ImportBatch:
    actor.require(Capability.RECON_IMPORT)
    if side not in SIDES:
        raise InvalidInput("side must be BANK or LEDGER", code="INVALID_SIDE")
    doc = require_clean(tx, document_version_id)
    if doc.media_type not in ("text/csv", "text/plain"):
        raise InvalidInput("Imports must be CSV files", code="MEDIA_TYPE")
    existing = tx.first(
        tx.select(ImportBatch).where(
            ImportBatch.side == side, ImportBatch.content_hash == doc.sha256
        )
    )
    if existing is not None:
        return existing  # the same file was already imported
    batch = tx.add(
        ImportBatch(
            side=side,
            document_version_id=doc.id,
            content_hash=doc.sha256 or "",
            mapping=mapping.model_dump(),
            created_by=actor.subject,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "reconciliation.import_requested",
        object_type="import_batch",
        object_id=batch.id,
        data={"side": side, "document_version_id": doc.id},
    )
    jobs.enqueue(tx, IMPORT_JOB, object_ref=batch.id, dedupe_key=str(batch.id))
    return batch


def parse_rows(data: bytes, mapping: Mapping) -> tuple[list[dict[str, Any]], list[str]]:
    text = data.decode("utf-8-sig", errors="strict")
    reader = csv.DictReader(io.StringIO(text))
    columns = set(reader.fieldnames or [])
    required = {mapping.external_id, mapping.booked_on, mapping.amount}
    optional = {c for c in (mapping.reference, mapping.description, mapping.currency) if c}
    missing = (required | optional) - columns
    if missing:
        return [], [f"Missing columns: {', '.join(sorted(missing))}"]
    rows, errors = [], []
    for number, raw in enumerate(reader, start=2):  # header is line 1
        if number - 1 > MAX_ROWS:
            errors.append(f"More than {MAX_ROWS} rows; split the file")
            break
        try:
            currency = (raw.get(mapping.currency) if mapping.currency else None) or (
                mapping.default_currency
            )
            money = Money.from_major(raw[mapping.amount].replace(",", "").strip(), currency)
            minor = -money.minor if mapping.negate_amounts else money.minor
            booked = datetime.strptime(raw[mapping.booked_on].strip(), mapping.date_format).date()
            external_id = raw[mapping.external_id].strip()
            if not external_id:
                raise ValueError("empty external id")
        except (MoneyError, ValueError, KeyError) as exc:
            errors.append(f"Row {number}: {exc}")
            continue
        reference = raw.get(mapping.reference, "").strip() if mapping.reference else None
        rows.append(
            {
                "row_number": number,
                "external_id": external_id[:100],
                "reference": reference or None,
                "booked_on": booked,
                "amount_minor": minor,
                "currency": money.currency,
                "description": (raw.get(mapping.description) or "")[:500]
                if mapping.description
                else None,
                "raw": dict(raw),
            }
        )
    return rows, errors


def run_import(tx: TenantSession, batch_id: uuid.UUID, data: bytes) -> None:
    batch = tx.get(ImportBatch, batch_id, for_update=True)
    if batch.state != "PENDING":
        return
    mapping = Mapping.model_validate(batch.mapping)
    try:
        rows, errors = parse_rows(data, mapping)
    except UnicodeDecodeError:
        rows, errors = [], ["File is not UTF-8 text"]
    imported = 0
    for row in rows:
        payload_hash = digest({k: v for k, v in row.items() if k != "row_number"})
        existing = tx.first(
            tx.select(SourceTransaction).where(
                SourceTransaction.side == batch.side,
                SourceTransaction.external_id == row["external_id"],
            )
        )
        if existing is not None:
            if existing.payload_hash != payload_hash:
                errors.append(
                    f"Row {row['row_number']}: {row['external_id']} conflicts with an earlier "
                    "import; original kept"
                )
            continue
        tx.add(
            SourceTransaction(
                batch_id=batch.id,
                row_number=row["row_number"],
                side=batch.side,
                external_id=row["external_id"],
                reference=row["reference"],
                normalized_reference=normalize_reference(row["reference"]),
                booked_on=row["booked_on"],
                amount_minor=row["amount_minor"],
                currency=row["currency"],
                description=row["description"],
                raw_row=row["raw"],
                payload_hash=payload_hash,
            )
        )
        imported += 1
    batch.row_count = len(rows) + sum(e.startswith("Row ") for e in errors)
    batch.imported_count = imported
    batch.errors = errors[:200]
    batch.state = "IMPORTED" if rows or not errors else "FAILED"
    tx.flush()
    audit.record(
        tx,
        "reconciliation.imported",
        object_type="import_batch",
        object_id=batch.id,
        data={"imported": imported, "errors": len(errors), "side": batch.side},
    )
    jobs.enqueue(tx, MATCH_JOB, dedupe_key=f"match:{batch.id}")


def batch_document(tx: TenantSession, batch_id: uuid.UUID) -> DocumentVersion:
    batch = tx.get(ImportBatch, batch_id)
    return tx.get(DocumentVersion, batch.document_version_id)


# -- matching -----------------------------------------------------------------------


def _open_rows(tx: TenantSession, side: str) -> list[SourceTransaction]:
    return list(
        tx.scalars(
            tx.select(SourceTransaction).where(
                SourceTransaction.side == side,
                SourceTransaction.status == "UNMATCHED",
            )
        )
    )


def run_matching(tx: TenantSession, actor_subject: str) -> dict[str, int]:
    """Propose exact matches and route everything else to exceptions. Re-runnable."""
    bank, ledger = _open_rows(tx, "BANK"), _open_rows(tx, "LEDGER")
    by_ref: dict[str, dict[str, list[SourceTransaction]]] = defaultdict(
        lambda: {"BANK": [], "LEDGER": []}
    )
    for row in bank + ledger:
        if row.normalized_reference:
            by_ref[row.normalized_reference][row.side].append(row)

    proposed = 0
    for ref, sides in by_ref.items():
        b_rows, l_rows = sides["BANK"], sides["LEDGER"]
        if len(b_rows) == 1 and len(l_rows) == 1:
            bank_row, ledger_row = b_rows[0], l_rows[0]
            if (
                bank_row.amount_minor == ledger_row.amount_minor
                and bank_row.currency == ledger_row.currency
            ):
                _propose(tx, bank_row, ledger_row, ref, actor_subject)
                proposed += 1

    exceptions = 0
    for row in bank + ledger:
        if row.status not in ("UNMATCHED",):
            continue
        kind, details = _classify(row, by_ref)
        if kind == "UNMATCHED":
            continue  # no counterpart yet; may arrive with a later import
        exceptions += _open_exception(tx, row, kind, details, actor_subject)
    audit.record(
        tx,
        "reconciliation.matching_run",
        object_type="organization",
        object_id=tx.organization_id,
        data={"proposed": proposed, "exceptions": exceptions},
    )
    return {"proposed": proposed, "exceptions": exceptions}


def _classify(
    row: SourceTransaction, by_ref: dict[str, dict[str, list[SourceTransaction]]]
) -> tuple[str, dict[str, Any]]:
    other = "LEDGER" if row.side == "BANK" else "BANK"
    if not row.normalized_reference:
        return "NO_REFERENCE", {}
    sides = by_ref[row.normalized_reference]
    counterparts, same_side = sides[other], sides[row.side]
    if not counterparts:
        return "UNMATCHED", {}
    ids = [str(c.id) for c in counterparts]
    if len(counterparts) > 1 or len(same_side) > 1:
        total = sum(c.amount_minor for c in counterparts)
        if len(counterparts) > 1 and total == row.amount_minor:
            return "SPLIT_PAYMENT_UNSUPPORTED", {"counterparts": ids}
        return "AMBIGUOUS_REFERENCE", {"counterparts": ids}
    c = counterparts[0]
    if c.currency != row.currency:
        return "CURRENCY_DIFFERENCE_UNSUPPORTED", {"counterparts": ids}
    return "AMOUNT_DIFFERENCE", {
        "counterparts": ids,
        "difference_minor": str(row.amount_minor - c.amount_minor),
        "hint": "Possible fee, partial payment, withholding or refund",
    }


def _open_exception(
    tx: TenantSession, row: SourceTransaction, kind: str, details: dict, actor_subject: str
) -> int:
    if tx.first(
        tx.select(ReconciliationException).where(
            ReconciliationException.source_transaction_id == row.id,
            ReconciliationException.kind == kind,
        )
    ):
        return 0
    money = Money(row.amount_minor, row.currency)
    case = tx.add(
        Case(
            module="reconciliation",
            title=(
                f"{row.side} {row.external_id} · {money.format()} · "
                f"{kind.replace('_', ' ').lower()}"
            ),
            status=CaseStatus.IN_REVIEW,
            outcome="REVIEW",
            subject_type="source_transaction",
            subject_id=row.id,
            created_by=actor_subject,
        )
    )
    tx.flush()
    tx.add(
        ReconciliationException(
            case_id=case.id, source_transaction_id=row.id, kind=kind, details=details
        )
    )
    row.status = "EXCEPTION"
    tx.flush()
    audit.record(
        tx,
        "reconciliation.exception_opened",
        object_type="case",
        object_id=case.id,
        data={"kind": kind, "source_transaction_id": row.id},
    )
    return 1


def _propose(
    tx: TenantSession, bank: SourceTransaction, ledger: SourceTransaction, ref: str, by: str
) -> None:
    group = tx.add(
        MatchGroup(
            match_type="EXACT_ONE_TO_ONE",
            proposed_by=by,
            basis={
                "reference": ref,
                "amount_minor": str(bank.amount_minor),
                "currency": bank.currency,
                "rule": "equal normalised reference, signed amount and currency",
            },
        )
    )
    tx.flush()
    for row in (bank, ledger):
        tx.add(
            MatchAllocation(
                group_id=group.id,
                source_transaction_id=row.id,
                side=row.side,
                allocated_minor=row.amount_minor,
            )
        )
        row.status = "PROPOSED"
    tx.flush()


def decide_match(
    tx: TenantSession,
    actor: Actor,
    group_id: uuid.UUID,
    *,
    approve: bool,
    expected_version: int,
    reason: str,
) -> MatchGroup:
    actor.require(Capability.RECON_MATCH_APPROVE)
    group = tx.get(MatchGroup, group_id, for_update=True)
    if group.version != expected_version:
        raise Conflict("The match changed since you loaded it", code="STALE_REVISION")
    if group.state != "PROPOSED":
        raise Conflict(f"Match is {group.state}", code="MATCH_NOT_PROPOSED")
    allocations = list(
        tx.scalars(tx.select(MatchAllocation).where(MatchAllocation.group_id == group.id))
    )
    # Fixed lock order: source rows by id.
    rows = [
        tx.get(SourceTransaction, a.source_transaction_id, for_update=True)
        for a in sorted(allocations, key=lambda a: str(a.source_transaction_id))
    ]
    group.version += 1
    group.decided_by, group.decided_at, group.reason = actor.subject, utcnow(), reason
    if not approve:
        group.state = "REJECTED"
        for row in rows:
            row.status = "UNMATCHED"
        audit.record(
            tx,
            "reconciliation.match_rejected",
            object_type="match_group",
            object_id=group.id,
            reason=reason,
        )
        return group

    sides = {r.side for r in rows}
    if (
        len(rows) != 2
        or sides != {"BANK", "LEDGER"}
        or rows[0].amount_minor != rows[1].amount_minor
        or rows[0].currency != rows[1].currency
    ):
        raise Conflict("Only exact one-to-one matches can be approved", code="UNSUPPORTED_MATCH")
    for row in rows:
        if row.allocated_minor != 0 or row.status != "PROPOSED":
            raise Conflict("A row is already allocated", code="ALREADY_ALLOCATED")
    for alloc, row in zip(
        sorted(allocations, key=lambda a: str(a.source_transaction_id)), rows, strict=True
    ):
        alloc.active = True
        row.allocated_minor = row.amount_minor
        row.status = "MATCHED"
    group.state = "APPROVED"
    tx.flush()
    audit.record(
        tx,
        "reconciliation.match_approved",
        object_type="match_group",
        object_id=group.id,
        reason=reason,
        data={"rows": [r.id for r in rows], **group.basis},
    )
    return group


def resolve_exception(
    tx: TenantSession,
    actor: Actor,
    exception_id: uuid.UUID,
    *,
    resolution_code: str,
    note: str,
) -> ReconciliationException:
    """Record a reviewed disposition. No accounting write-back: it is exported."""
    actor.require(Capability.RECON_MATCH_APPROVE)
    exc = tx.get(ReconciliationException, exception_id, for_update=True)
    if exc.state != "OPEN":
        raise Conflict("Exception already resolved", code="ALREADY_RESOLVED")
    exc.state = "RESOLVED"
    exc.resolution_code, exc.resolution_note = resolution_code, note
    exc.resolved_by, exc.updated_at = actor.subject, utcnow()
    case = cases.get_for_update(tx, exc.case_id)
    cases.transition(tx, case, CaseStatus.RESOLVED, reason=f"{resolution_code}: {note}")
    audit.record(
        tx,
        "reconciliation.exception_resolved",
        object_type="case",
        object_id=case.id,
        reason=note,
        data={
            "resolution_code": resolution_code,
            "source_transaction_id": exc.source_transaction_id,
        },
    )
    return exc


def row_view(row: SourceTransaction) -> dict[str, Any]:
    money = Money(row.amount_minor, row.currency)
    return {
        "id": row.id,
        "side": row.side,
        "external_id": row.external_id,
        "reference": row.reference,
        "booked_on": row.booked_on,
        "amount": {**money.to_api(), "formatted": money.format()},
        "description": row.description,
        "status": row.status,
        "lineage": {"batch_id": row.batch_id, "row_number": row.row_number},
        "raw_row": row.raw_row,
    }


def export_rows(tx: TenantSession) -> str:
    """Approved matches and reviewed exception dispositions as CSV."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "record_type",
            "id",
            "bank_external_id",
            "ledger_external_id",
            "reference",
            "amount_minor",
            "currency",
            "disposition",
            "decided_by",
        ]
    )
    for group in tx.scalars(tx.select(MatchGroup).where(MatchGroup.state == "APPROVED")):
        allocs = tx.scalars(tx.select(MatchAllocation).where(MatchAllocation.group_id == group.id))
        ext = {
            a.side: tx.get(SourceTransaction, a.source_transaction_id).external_id for a in allocs
        }
        writer.writerow(
            [
                "MATCH",
                group.id,
                ext.get("BANK"),
                ext.get("LEDGER"),
                group.basis["reference"],
                group.basis["amount_minor"],
                group.basis["currency"],
                "MATCHED",
                group.decided_by,
            ]
        )
    for exc in tx.scalars(
        tx.select(ReconciliationException).where(ReconciliationException.state == "RESOLVED")
    ):
        row = tx.get(SourceTransaction, exc.source_transaction_id)
        writer.writerow(
            [
                "EXCEPTION",
                exc.id,
                row.external_id if row.side == "BANK" else "",
                row.external_id if row.side == "LEDGER" else "",
                row.reference,
                row.amount_minor,
                row.currency,
                f"{exc.kind}:{exc.resolution_code}",
                exc.resolved_by,
            ]
        )
    return out.getvalue()
