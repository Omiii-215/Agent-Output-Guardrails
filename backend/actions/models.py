"""M5 action gateway records: proposals, approvals, intents, attempts, spend.

``APPROVED`` does not mean paid, ``SUBMITTED`` does not mean settled and
``UNKNOWN`` does not mean failed: approval state and external execution state
are separate fields on separate records.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


def _fk(local: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(
        ["organization_id", local], [f"{table}.organization_id", f"{table}.id"]
    )


class ProposalState:
    PREFLIGHT_PENDING = "PREFLIGHT_PENDING"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    SUPERSEDED = "SUPERSEDED"
    INTENT_CREATED = "INTENT_CREATED"


ACTIVE_PROPOSAL_STATES = frozenset(
    {
        ProposalState.PREFLIGHT_PENDING,
        ProposalState.READY_FOR_APPROVAL,
        ProposalState.NEEDS_REVIEW,
        ProposalState.AWAITING_APPROVAL,
        ProposalState.APPROVED,
        ProposalState.INTENT_CREATED,
    }
)


class ActionProposal(TenantMixin, TimestampMixin, Base):
    """A server-validated, frozen action payload. Changing it means a new proposal."""

    __tablename__ = "action_proposal"
    __table_args__ = (
        _fk("case_id", "case_record"),
        Index("ix_action_proposal_case", "organization_id", "case_id"),
    )

    case_id: Mapped[uuid.UUID]
    maker_subject: Mapped[str] = mapped_column(String(200))
    maker_actor_type: Mapped[str] = mapped_column(String(20))
    action_type: Mapped[str] = mapped_column(String(30))
    mode: Mapped[str] = mapped_column(String(20))
    canonical_payload: Mapped[dict[str, Any]]
    payload_algorithm: Mapped[str] = mapped_column(String(20))
    digest: Mapped[str] = mapped_column(String(80))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    source_revision_map: Mapped[dict[str, Any]] = mapped_column(default=dict)
    state: Mapped[str] = mapped_column(String(30), default=ProposalState.PREFLIGHT_PENDING)
    state_reason: Mapped[str | None] = mapped_column(String(1000))
    revision: Mapped[int] = mapped_column(default=1)
    superseded_by: Mapped[uuid.UUID | None]
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class ActionControl(TenantMixin, Base):
    """Per-organization emergency stop. Applies to new claims immediately."""

    __tablename__ = "action_control"
    __table_args__ = (UniqueConstraint("organization_id"),)

    halted: Mapped[bool] = mapped_column(default=False)
    reason: Mapped[str | None] = mapped_column(String(1000))
    changed_by: Mapped[str | None] = mapped_column(String(200))
    changed_at: Mapped[datetime] = mapped_column(default=utcnow)


class SpendBucket(TenantMixin, Base):
    """Committed and reserved spend for one currency and window.

    Locked (SELECT … FOR UPDATE) before checking available = limit - committed
    - reserved, so concurrent requests cannot overspend.
    """

    __tablename__ = "spend_bucket"
    __table_args__ = (
        UniqueConstraint("organization_id", "scope", "currency", "window", "window_start"),
    )

    scope: Mapped[str] = mapped_column(String(40), default="ORGANIZATION")
    currency: Mapped[str] = mapped_column(String(3))
    window: Mapped[str] = mapped_column(String(10))  # DAY | MONTH
    window_start: Mapped[date]
    limit_minor: Mapped[int] = mapped_column(BigInteger)
    committed_minor: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_minor: Mapped[int] = mapped_column(BigInteger, default=0)


class SpendReservation(TenantMixin, TimestampMixin, Base):
    __tablename__ = "spend_reservation"
    __table_args__ = (
        _fk("bucket_id", "spend_bucket"),
        UniqueConstraint("organization_id", "intent_id", "bucket_id"),
    )

    bucket_id: Mapped[uuid.UUID]
    intent_id: Mapped[uuid.UUID]
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    state: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE|COMMITTED|RELEASED
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class IntentState:
    CREATED = "CREATED"
    RESERVED = "RESERVED"
    SUBMITTING = "SUBMITTING"
    ACCEPTED = "ACCEPTED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    SETTLED = "SETTLED"
    REVERSED = "REVERSED"
    INVALIDATED = "INVALIDATED"


class ActionIntent(TenantMixin, TimestampMixin, Base):
    """One logical execution of an approved proposal, with a stable provider key."""

    __tablename__ = "action_intent"
    __table_args__ = (
        _fk("proposal_id", "action_proposal"),
        _fk("approval_request_id", "approval_request"),
        UniqueConstraint("organization_id", "proposal_id"),
        UniqueConstraint("organization_id", "provider_idempotency_key"),
    )

    proposal_id: Mapped[uuid.UUID]
    approval_request_id: Mapped[uuid.UUID]
    case_id: Mapped[uuid.UUID]
    action_digest: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(20))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(20), default=IntentState.CREATED)
    state_reason: Mapped[str | None] = mapped_column(String(1000))
    provider: Mapped[str] = mapped_column(String(40))
    provider_idempotency_key: Mapped[str] = mapped_column(String(200))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(default=0)
    created_by: Mapped[str] = mapped_column(String(200))
    claimed_at: Mapped[datetime | None]
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow)


class ActionAttempt(TenantMixin, TimestampMixin, Base):
    __tablename__ = "action_attempt"
    __append_only__ = True
    __table_args__ = (_fk("intent_id", "action_intent"),)

    intent_id: Mapped[uuid.UUID] = mapped_column(index=True)
    attempt_number: Mapped[int]
    kind: Mapped[str] = mapped_column(String(20))  # SUBMIT | STATUS | WEBHOOK
    provider_idempotency_key: Mapped[str] = mapped_column(String(200))
    request_digest: Mapped[str] = mapped_column(String(80))
    outcome: Mapped[str] = mapped_column(String(20))
    provider_reference: Mapped[str | None] = mapped_column(String(100))
    response_code: Mapped[str | None] = mapped_column(String(60))


class WebhookReceipt(TenantMixin, Base):
    __tablename__ = "webhook_receipt"
    __table_args__ = (UniqueConstraint("organization_id", "connector", "provider_event_id"),)

    connector: Mapped[str] = mapped_column(String(40))
    provider_event_id: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]]
    payload_hash: Mapped[str] = mapped_column(String(80))
    processing_state: Mapped[str] = mapped_column(String(20), default="RECEIVED")
    received_at: Mapped[datetime] = mapped_column(default=utcnow)
