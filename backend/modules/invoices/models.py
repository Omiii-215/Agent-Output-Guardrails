"""Invoice preflight data (module M1).

Invoices and beneficiaries are versioned: a correction or a changed bank
account creates a new immutable version, so reviewers can reconstruct what
was known when a decision was made.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.persistence.base import Base, TenantMixin, TimestampMixin


def _fk(local: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["organization_id", local], [f"{table}.organization_id", f"{table}.id"]
    )


class Vendor(TenantMixin, TimestampMixin, Base):
    __tablename__ = "vendor"
    __table_args__ = (UniqueConstraint("organization_id", "normalized_name"),)

    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    current_beneficiary_id: Mapped[uuid.UUID | None]
    created_by: Mapped[str] = mapped_column(String(200))


class BeneficiaryVersion(TenantMixin, TimestampMixin, Base):
    """Bank details for a vendor. A changed account is a new, unverified version."""

    __tablename__ = "beneficiary_version"
    __table_args__ = (
        _fk("vendor_id", "vendor"),
        UniqueConstraint("organization_id", "vendor_id", "revision"),
    )

    vendor_id: Mapped[uuid.UUID]
    revision: Mapped[int]
    account_holder: Mapped[str] = mapped_column(String(200))
    account_ciphertext: Mapped[str] = mapped_column(String(500))
    account_fingerprint: Mapped[str] = mapped_column(String(80))
    account_last4: Mapped[str] = mapped_column(String(4))
    ifsc: Mapped[str] = mapped_column(String(11))
    verification_status: Mapped[str] = mapped_column(String(20), default="UNVERIFIED")
    verification_note: Mapped[str | None] = mapped_column(String(1000))
    verified_by: Mapped[str | None] = mapped_column(String(200))
    verified_at: Mapped[datetime | None]
    created_by: Mapped[str] = mapped_column(String(200))


class Invoice(TenantMixin, TimestampMixin, Base):
    __tablename__ = "invoice"
    __table_args__ = (
        _fk("case_id", "case_record"),
        _fk("vendor_id", "vendor"),
        UniqueConstraint("organization_id", "document_version_id"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(index=True)
    vendor_id: Mapped[uuid.UUID]
    document_version_id: Mapped[uuid.UUID | None]
    current_version: Mapped[int] = mapped_column(default=1)


class InvoiceVersion(TenantMixin, TimestampMixin, Base):
    __tablename__ = "invoice_version"
    __append_only__ = True
    __table_args__ = (
        _fk("invoice_id", "invoice"),
        UniqueConstraint("organization_id", "invoice_id", "version"),
        Index("ix_invoice_candidate", "organization_id", "vendor_id", "number_normalized"),
    )

    invoice_id: Mapped[uuid.UUID]
    version: Mapped[int]
    vendor_id: Mapped[uuid.UUID]
    beneficiary_version_id: Mapped[uuid.UUID | None]
    number_raw: Mapped[str | None] = mapped_column(String(100))
    number_normalized: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[date | None]
    due_date: Mapped[date | None]
    currency: Mapped[str | None] = mapped_column(String(3))
    subtotal_minor: Mapped[int | None] = mapped_column(BigInteger)
    tax_minor: Mapped[int | None] = mapped_column(BigInteger)
    total_minor: Mapped[int | None] = mapped_column(BigInteger)
    po_number: Mapped[str | None] = mapped_column(String(100))
    lines: Mapped[list[Any]] = mapped_column(default=list)
    field_status: Mapped[dict[str, Any]] = mapped_column(default=dict)
    extraction_meta: Mapped[dict[str, Any]] = mapped_column(default=dict)
    source: Mapped[str] = mapped_column(String(20))  # MANUAL | EXTRACTED | CORRECTION
    reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[str] = mapped_column(String(200))


class PaymentRecord(TenantMixin, TimestampMixin, Base):
    """Paid-invoice history imported from the customer's systems (or the simulator)."""

    __tablename__ = "payment_record"
    __table_args__ = (
        _fk("vendor_id", "vendor"),
        UniqueConstraint("organization_id", "source", "external_reference"),
        Index("ix_payment_candidate", "organization_id", "vendor_id", "number_normalized"),
    )

    vendor_id: Mapped[uuid.UUID]
    number_normalized: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    paid_on: Mapped[date]
    external_reference: Mapped[str] = mapped_column(String(200))
    source: Mapped[str] = mapped_column(String(20))  # IMPORT | SIMULATION
