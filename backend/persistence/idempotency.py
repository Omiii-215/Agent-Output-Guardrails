"""Idempotency-Key handling for retriable mutations (LLD §6).

The same tenant, actor scope, route, key and canonical body return the
original response. The same key with another body is ``409
IDEMPOTENCY_CONFLICT``. The record and the business change commit in one
transaction, so concurrent identical calls converge on one operation: the
second insert waits on the unique index and then replays the stored result.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.canonical import digest
from backend.domain.clock import utcnow
from backend.errors import Conflict, InvalidInput
from backend.identity.actor import Actor
from backend.persistence.base import Base, TenantMixin
from backend.persistence.database import Database, TenantSession


class IdempotencyRecord(TenantMixin, Base):
    __tablename__ = "idempotency_record"
    __table_args__ = (UniqueConstraint("organization_id", "actor_scope", "route", "key"),)

    actor_scope: Mapped[str] = mapped_column(String(200))
    route: Mapped[str] = mapped_column(String(200))
    key: Mapped[str] = mapped_column(String(200))
    request_digest: Mapped[str] = mapped_column(String(80))
    response_status: Mapped[int]
    response_body: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


@dataclass(frozen=True)
class IdempotentResult:
    status: int
    body: dict[str, Any]
    replayed: bool


def _json_safe(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value, default=str))


def _validate_key(key: str) -> str:
    key = key.strip()
    if not 8 <= len(key) <= 200:
        raise InvalidInput("Idempotency-Key must be 8-200 characters", code="IDEMPOTENCY_KEY")
    return key


def _existing(
    db: Database, actor: Actor, route: str, key: str, request_digest: str
) -> IdempotentResult:
    with db.tenant(actor.organization_id, subject=actor.subject) as tx:
        record = tx.first(
            tx.select(IdempotencyRecord).where(
                IdempotencyRecord.actor_scope == actor.subject,
                IdempotencyRecord.route == route,
                IdempotencyRecord.key == key,
            )
        )
    if record is None:  # pragma: no cover - the conflicting insert rolled back
        raise Conflict("Concurrent request in progress; retry", code="IDEMPOTENCY_IN_PROGRESS")
    if record.request_digest != request_digest:
        raise Conflict(
            "Idempotency-Key was already used with a different request",
            code="IDEMPOTENCY_CONFLICT",
        )
    return IdempotentResult(record.response_status, dict(record.response_body), replayed=True)


def run(
    db: Database,
    actor: Actor,
    *,
    route: str,
    key: str | None,
    body: Any,
    operation: Callable[[TenantSession], tuple[int, dict[str, Any]]],
) -> IdempotentResult:
    """Run ``operation`` once per (actor, route, key, body)."""
    if key is None:
        with db.tenant(actor.organization_id, subject=actor.subject, actor=actor) as tx:
            status, response = operation(tx)
        return IdempotentResult(status, _json_safe(response), replayed=False)

    key = _validate_key(key)
    request_digest = digest({"route": route, "body": body})
    try:
        with db.tenant(actor.organization_id, subject=actor.subject, actor=actor) as tx:
            existing = tx.first(
                tx.select(IdempotencyRecord).where(
                    IdempotencyRecord.actor_scope == actor.subject,
                    IdempotencyRecord.route == route,
                    IdempotencyRecord.key == key,
                )
            )
            if existing is None:
                record = tx.add(
                    IdempotencyRecord(
                        id=uuid.uuid4(),
                        actor_scope=actor.subject,
                        route=route,
                        key=key,
                        request_digest=request_digest,
                        response_status=0,
                    )
                )
                tx.flush()  # takes the unique-index slot; concurrent twins wait here
                status, response = operation(tx)
                response = _json_safe(response)
                record.response_status = status
                record.response_body = response
                return IdempotentResult(status, response, replayed=False)
    except IntegrityError:
        pass  # a concurrent identical request committed first
    return _existing(db, actor, route, key, request_digest)
