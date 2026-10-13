"""Approval requests bound to one exact proposal digest, and reviewer decisions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


class RequestState:
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    EXPIRED = "EXPIRED"


class ApprovalRequest(TenantMixin, TimestampMixin, Base):
    __tablename__ = "approval_request"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "proposal_id"],
            ["action_proposal.organization_id", "action_proposal.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "evaluation_id"], ["evaluation.organization_id", "evaluation.id"]
        ),
    )

    proposal_id: Mapped[uuid.UUID] = mapped_column(index=True)
    evaluation_id: Mapped[uuid.UUID]
    action_digest: Mapped[str] = mapped_column(String(80))
    policy_version_id: Mapped[uuid.UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    requirements: Mapped[dict[str, Any]]
    required_count: Mapped[int]
    expires_at: Mapped[datetime]
    state: Mapped[str] = mapped_column(String(20), default=RequestState.PENDING)
    state_reason: Mapped[str | None] = mapped_column(String(1000))
    requested_by: Mapped[str] = mapped_column(String(200))
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApprovalDecision(TenantMixin, TimestampMixin, Base):
    __tablename__ = "approval_decision"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "request_id"],
            ["approval_request.organization_id", "approval_request.id"],
        ),
        UniqueConstraint("organization_id", "request_id", "actor_subject"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_subject: Mapped[str] = mapped_column(String(200))
    membership_id: Mapped[uuid.UUID]
    roles_at_decision: Mapped[list[Any]]
    authorization_revision: Mapped[int]
    decision: Mapped[str] = mapped_column(String(10))  # APPROVE | REJECT
    reason: Mapped[str] = mapped_column(String(1000))
    action_digest: Mapped[str] = mapped_column(String(80))
