"""Case lifecycle, assignment, comments and the review queue."""

from __future__ import annotations

import base64
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, or_

from backend.cases.models import Case, CaseComment, CaseStatus
from backend.domain.clock import utcnow
from backend.errors import Conflict, InvalidInput
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.modules.registry import require_enabled
from backend.persistence.database import TenantSession
from backend.telemetry import audit
from backend.telemetry.audit import AuditEvent

S = CaseStatus

TRANSITIONS: dict[str, frozenset[str]] = {
    S.RECEIVED: frozenset({S.EXTRACTING, S.READY_TO_EVALUATE, S.NEEDS_INFORMATION, S.CLOSED}),
    S.EXTRACTING: frozenset({S.NEEDS_INFORMATION, S.READY_TO_EVALUATE}),
    S.NEEDS_INFORMATION: frozenset({S.READY_TO_EVALUATE, S.EXTRACTING, S.CLOSED}),
    S.READY_TO_EVALUATE: frozenset({S.EVALUATING, S.NEEDS_INFORMATION}),
    S.EVALUATING: frozenset({S.IN_REVIEW, S.READY_TO_EVALUATE}),
    S.IN_REVIEW: frozenset(
        {S.NEEDS_INFORMATION, S.READY_TO_EVALUATE, S.READY_FOR_ACTION, S.RESOLVED, S.CLOSED}
    ),
    S.READY_FOR_ACTION: frozenset({S.IN_REVIEW, S.ACTION_PENDING}),
    S.ACTION_PENDING: frozenset({S.RESOLVED, S.IN_REVIEW}),
    S.RESOLVED: frozenset(),
    S.CLOSED: frozenset(),
}

TERMINAL = frozenset({S.RESOLVED, S.CLOSED})


def create_case(
    tx: TenantSession,
    actor: Actor,
    *,
    module: str,
    title: str,
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    status: str = S.RECEIVED,
    due_at: datetime | None = None,
) -> Case:
    require_enabled(module)
    case = tx.add(
        Case(
            module=module,
            title=title,
            status=status,
            subject_type=subject_type,
            subject_id=subject_id,
            owner_subject=actor.subject if actor.is_human else None,
            created_by=actor.subject,
            due_at=due_at,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "case.created",
        object_type="case",
        object_id=case.id,
        data={"module": module, "status": status, "subject_id": subject_id},
    )
    return case


def check_revision(case: Case, expected_revision: int | None) -> None:
    if expected_revision is not None and expected_revision != case.revision:
        raise Conflict(
            "The case changed since you loaded it",
            code="STALE_REVISION",
            details={"expected": expected_revision, "current": case.revision},
        )


def transition(
    tx: TenantSession,
    case: Case,
    to_status: str,
    *,
    reason: str | None = None,
    data: dict[str, Any] | None = None,
) -> Case:
    if to_status == case.status:
        return case
    if to_status not in TRANSITIONS[case.status]:
        raise Conflict(
            f"Case cannot move from {case.status} to {to_status}",
            code="INVALID_TRANSITION",
            details={"from": case.status, "to": to_status},
        )
    previous = case.status
    case.status = to_status
    touch(case)
    audit.record(
        tx,
        "case.transitioned",
        object_type="case",
        object_id=case.id,
        reason=reason,
        data={"from": previous, "to": to_status, "revision": case.revision, **(data or {})},
    )
    return case


def touch(case: Case) -> None:
    case.revision += 1
    case.updated_at = utcnow()


def get_for_update(tx: TenantSession, case_id: uuid.UUID) -> Case:
    return tx.get(Case, case_id, for_update=True)


def assign(
    tx: TenantSession,
    actor: Actor,
    case_id: uuid.UUID,
    owner_subject: str,
    expected_revision: int,
) -> Case:
    actor.require(Capability.CASE_WRITE)
    case = get_for_update(tx, case_id)
    check_revision(case, expected_revision)
    case.owner_subject = owner_subject
    touch(case)
    audit.record(
        tx, "case.assigned", object_type="case", object_id=case.id, data={"owner": owner_subject}
    )
    return case


def close(
    tx: TenantSession, actor: Actor, case_id: uuid.UUID, reason: str, expected_revision: int
) -> Case:
    actor.require(Capability.CASE_WRITE)
    case = get_for_update(tx, case_id)
    check_revision(case, expected_revision)
    case.closed_reason = reason
    return transition(tx, case, S.CLOSED, reason=reason)


def add_comment(tx: TenantSession, actor: Actor, case_id: uuid.UUID, body: str) -> CaseComment:
    actor.require(Capability.CASE_READ)
    tx.get(Case, case_id)
    comment = tx.add(CaseComment(case_id=case_id, author_subject=actor.subject, body=body))
    tx.flush()
    return comment


def comments(tx: TenantSession, case_id: uuid.UUID) -> list[CaseComment]:
    tx.get(Case, case_id)
    return list(
        tx.scalars(
            tx.select(CaseComment)
            .where(CaseComment.case_id == case_id)
            .order_by(CaseComment.created_at)
        )
    )


def history(
    tx: TenantSession, case_id: uuid.UUID, related_ids: list[uuid.UUID]
) -> list[AuditEvent]:
    tx.get(Case, case_id)
    ids = [case_id, *related_ids]
    return list(
        tx.scalars(
            tx.select(AuditEvent)
            .where(AuditEvent.object_id.in_(ids))
            .order_by(AuditEvent.occurred_at, AuditEvent.id)
        )
    )


# -- queue ---------------------------------------------------------------------


def _encode_cursor(case: Case) -> str:
    raw = f"{case.updated_at.isoformat()}|{case.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        stamp, ident = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
        return datetime.fromisoformat(stamp), uuid.UUID(ident)
    except ValueError:
        raise InvalidInput("Invalid cursor", code="INVALID_CURSOR") from None


def queue(
    tx: TenantSession,
    *,
    status: list[str] | None = None,
    module: str | None = None,
    owner: str | None = None,
    open_only: bool = False,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[Case], str | None]:
    stmt = tx.select(Case)
    if status:
        stmt = stmt.where(Case.status.in_(status))
    if open_only:
        stmt = stmt.where(Case.status.not_in(TERMINAL))
    if module:
        stmt = stmt.where(Case.module == module)
    if owner:
        stmt = stmt.where(Case.owner_subject == owner)
    if cursor:
        stamp, ident = _decode_cursor(cursor)
        stmt = stmt.where(
            or_(Case.updated_at < stamp, and_(Case.updated_at == stamp, Case.id < ident))
        )
    stmt = stmt.order_by(Case.updated_at.desc(), Case.id.desc()).limit(limit + 1)
    rows = list(tx.scalars(stmt))
    next_cursor = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], next_cursor
