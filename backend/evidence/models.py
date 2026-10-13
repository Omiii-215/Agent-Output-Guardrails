"""Documents and evidence items.

Document bytes live in private object storage; the database holds metadata,
hashes and access relationships. Each upload is a new immutable version of a
logical document. Evidence items point at an exact source location (page
region, CSV row, JSON path) and are append-only.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


class DocumentStatus:
    PENDING_UPLOAD = "PENDING_UPLOAD"
    QUARANTINED = "QUARANTINED"
    CLEAN = "CLEAN"
    REJECTED = "REJECTED"


class DocumentVersion(TenantMixin, TimestampMixin, Base):
    __tablename__ = "document_version"
    __table_args__ = (UniqueConstraint("organization_id", "document_id", "version"),)

    document_id: Mapped[uuid.UUID]
    version: Mapped[int]
    object_key: Mapped[str] = mapped_column(String(300))
    original_name: Mapped[str] = mapped_column(String(255))
    media_type: Mapped[str] = mapped_column(String(100))
    declared_size: Mapped[int] = mapped_column(BigInteger)
    declared_sha256: Mapped[str] = mapped_column(String(80))
    size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING_UPLOAD)
    malware_status: Mapped[str] = mapped_column(String(20), default="NOT_SCANNED")
    rejection_reason: Mapped[str | None] = mapped_column(String(200))
    uploaded_by: Mapped[str] = mapped_column(String(200))
    verified_at: Mapped[datetime | None]


class EvidenceItem(TenantMixin, Base):
    __tablename__ = "evidence_item"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "document_version_id"],
            ["document_version.organization_id", "document_version.id"],
        ),
    )

    source_type: Mapped[str] = mapped_column(String(40))  # document | import_row | provider | user
    source_ref: Mapped[str] = mapped_column(String(300))
    document_version_id: Mapped[uuid.UUID | None]
    locator: Mapped[dict[str, Any]] = mapped_column(default=dict)
    excerpt: Mapped[str | None] = mapped_column(String(2000))
    integrity_hash: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(default=utcnow)
    valid_until: Mapped[datetime | None]
    recorded_by: Mapped[str] = mapped_column(String(200))
