"""Review cases.

Case progress (``status``) and the latest policy ``outcome`` are separate
fields: a BLOCK outcome is evidence for review, not a terminal verdict.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKeyConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


class CaseStatus:
    RECEIVED = "RECEIVED"
    EXTRACTING = "EXTRACTING"
    NEEDS_INFORMATION = "NEEDS_INFORMATION"
    READY_TO_EVALUATE = "READY_TO_EVALUATE"
    EVALUATING = "EVALUATING"
    IN_REVIEW = "IN_REVIEW"
    READY_FOR_ACTION = "READY_FOR_ACTION"
    ACTION_PENDING = "ACTION_PENDING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class Case(TenantMixin, TimestampMixin, Base):
    __tablename__ = "case_record"
    __table_args__ = (
        Index("ix_case_queue", "organization_id", "status", "updated_at"),
        Index("ix_case_subject", "organization_id", "subject_type", "subject_id"),
    )

    module: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default=CaseStatus.RECEIVED)
    outcome: Mapped[str | None] = mapped_column(String(20))
    subject_type: Mapped[str | None] = mapped_column(String(40))
    subject_id: Mapped[uuid.UUID | None]
    owner_subject: Mapped[str | None] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(default=1)
    due_at: Mapped[datetime | None]
    closed_reason: Mapped[str | None] = mapped_column(String(1000))
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class CaseComment(TenantMixin, TimestampMixin, Base):
    __tablename__ = "case_comment"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"], ["case_record.organization_id", "case_record.id"]
        ),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(index=True)
    author_subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(4000))
