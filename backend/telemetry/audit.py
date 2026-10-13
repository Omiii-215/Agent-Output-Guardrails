"""Append-only audit history.

Audit events record actor, action, object, reason, trace and the versions a
decision depended on. Ordinary runtime roles can only insert: PostgreSQL
grants plus a trigger (and an equivalent SQLite trigger) reject UPDATE and
DELETE. Audit events are not a financial ledger.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.canonical import digest
from backend.domain.clock import utcnow
from backend.persistence.base import Base, TenantMixin
from backend.persistence.database import TenantSession
from backend.telemetry.tracing import current_trace_id


class AuditEvent(TenantMixin, Base):
    __tablename__ = "audit_event"
    __append_only__ = True
    __table_args__ = (
        Index("ix_audit_event_object", "organization_id", "object_type", "object_id"),
    )

    actor_type: Mapped[str] = mapped_column(String(20))  # user | service | system
    actor_id: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(100))
    object_type: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[uuid.UUID | None]
    reason: Mapped[str | None] = mapped_column(String(1000))
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    change_digest: Mapped[str] = mapped_column(String(80))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    simulated: Mapped[bool] = mapped_column(default=False)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)


def _actor_fields(actor: Any) -> tuple[str, str]:
    if actor is None:
        return "system", "system"
    kind = getattr(actor, "actor_type", "user")
    return kind, str(getattr(actor, "subject", actor))


def record(
    db: TenantSession,
    action: str,
    *,
    object_type: str,
    object_id: uuid.UUID | None,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
    simulated: bool = False,
    actor: Any = None,
) -> AuditEvent:
    actor_type, actor_id = _actor_fields(actor if actor is not None else db.actor)
    payload = data or {}
    event = AuditEvent(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        reason=reason,
        data=payload,
        change_digest=digest(
            {"action": action, "object_id": object_id, "data": payload, "reason": reason}
        ),
        trace_id=current_trace_id(),
        simulated=simulated,
    )
    db.add(event)
    return event
