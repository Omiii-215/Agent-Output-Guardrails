"""Reconciliation records (module M2).

Imported rows keep their original values and lineage (batch + row number).
The first release supports exact one-to-one, full-amount matches only; the
allocation schema leaves room for a later, separately validated N-to-M release.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


def _fk(local: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["organization_id", local], [f"{table}.organization_id", f"{table}.id"]
    )


class ImportBatch(TenantMixin, TimestampMixin, Base):
    __tablename__ = "import_batch"
    __table_args__ = (
        _fk("document_version_id", "document_version"),
        UniqueConstraint("organization_id", "side", "content_hash"),
    )

    side: Mapped[str] = mapped_column(String(10))  # BANK | LEDGER
    document_version_id: Mapped[uuid.UUID]
    content_hash: Mapped[str] = mapped_column(String(80))
    mapping: Mapped[dict[str, Any]]
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    row_count: Mapped[int] = mapped_column(default=0)
    imported_count: Mapped[int] = mapped_column(default=0)
    errors: Mapped[list[Any]] = mapped_column(default=list)
    created_by: Mapped[str] = mapped_column(String(200))


class SourceTransaction(TenantMixin, TimestampMixin, Base):
    __tablename__ = "source_transaction"
    __table_args__ = (
        _fk("batch_id", "import_batch"),
        UniqueConstraint("organization_id", "side", "external_id"),
        Index("ix_source_txn_reference", "organization_id", "side", "normalized_reference"),
    )

    batch_id: Mapped[uuid.UUID]
    row_number: Mapped[int]
    side: Mapped[str] = mapped_column(String(10))
    external_id: Mapped[str] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(200))
    normalized_reference: Mapped[str | None] = mapped_column(String(200))
    booked_on: Mapped[date]
    amount_minor: Mapped[int] = mapped_column(BigInteger)  # signed: outflow negative
    currency: Mapped[str] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(String(500))
    raw_row: Mapped[dict[str, Any]]
    payload_hash: Mapped[str] = mapped_column(String(80))
    allocated_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="UNMATCHED"
    )  # |PROPOSED|MATCHED|EXCEPTION


class MatchGroup(TenantMixin, TimestampMixin, Base):
    __tablename__ = "match_group"

    match_type: Mapped[str] = mapped_column(String(30))  # EXACT_ONE_TO_ONE
    state: Mapped[str] = mapped_column(String(20), default="PROPOSED")
    version: Mapped[int] = mapped_column(default=1)
    basis: Mapped[dict[str, Any]] = mapped_column(default=dict)
    proposed_by: Mapped[str] = mapped_column(String(200))
    decided_by: Mapped[str | None] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(String(1000))
    decided_at: Mapped[datetime | None]


class MatchAllocation(TenantMixin, TimestampMixin, Base):
    __tablename__ = "match_allocation"
    __table_args__ = (
        _fk("group_id", "match_group"),
        _fk("source_transaction_id", "source_transaction"),
        # At most one active allocation per source row (one-to-one, full amount).
        Index(
            "uq_match_allocation_active",
            "organization_id",
            "source_transaction_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active"),
        ),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(index=True)
    source_transaction_id: Mapped[uuid.UUID]
    side: Mapped[str] = mapped_column(String(10))
    allocated_minor: Mapped[int] = mapped_column(BigInteger)
    active: Mapped[bool] = mapped_column(default=False)


class ReconciliationException(TenantMixin, TimestampMixin, Base):
    __tablename__ = "reconciliation_exception"
    __table_args__ = (
        _fk("case_id", "case_record"),
        _fk("source_transaction_id", "source_transaction"),
        UniqueConstraint("organization_id", "source_transaction_id", "kind"),
    )

    case_id: Mapped[uuid.UUID]
    source_transaction_id: Mapped[uuid.UUID]
    kind: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict[str, Any]] = mapped_column(default=dict)
    state: Mapped[str] = mapped_column(String(20), default="OPEN")
    resolution_code: Mapped[str | None] = mapped_column(String(60))
    resolution_note: Mapped[str | None] = mapped_column(String(1000))
    resolved_by: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)
