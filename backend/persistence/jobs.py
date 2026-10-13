"""Durable jobs and the transactional outbox (ADR 0004).

* ``enqueue`` and ``emit`` write in the caller's transaction, so business state
  and follow-up work commit together.
* Workers claim jobs with ``FOR UPDATE SKIP LOCKED`` and a lease token. A job is
  completed only while its token is current; abandoned leases are reaped.
* Retryable failures back off exponentially with jitter until ``max_attempts``,
  then the job is DEAD and visible to operators.
* Job and outbox rows hold references only. Handlers load tenant payloads inside
  the job's organization context.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.domain.canonical import to_jsonable
from backend.domain.clock import new_id, utcnow
from backend.persistence.base import Base
from backend.persistence.database import Database, TenantSession
from backend.telemetry.tracing import redact


class JobState:
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    DEAD = "DEAD"


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        UniqueConstraint("organization_id", "job_type", "dedupe_key"),
        Index("ix_job_ready", "state", "available_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"))
    job_type: Mapped[str] = mapped_column(String(80))
    object_ref: Mapped[uuid.UUID | None]
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(20), default=JobState.READY)
    available_at: Mapped[datetime] = mapped_column(default=utcnow)
    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    lease_token: Mapped[uuid.UUID | None]
    lease_until: Mapped[datetime | None]
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    completed_at: Mapped[datetime | None]


class OutboxEvent(Base):
    __tablename__ = "outbox_event"
    __table_args__ = (Index("ix_outbox_unpublished", "published_at", "occurred_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"))
    event_type: Mapped[str] = mapped_column(String(80))
    schema_version: Mapped[int] = mapped_column(default=1)
    aggregate_id: Mapped[uuid.UUID]
    aggregate_revision: Mapped[int] = mapped_column(default=0)
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    occurred_at: Mapped[datetime] = mapped_column(default=utcnow)
    published_at: Mapped[datetime | None]


class LeaseLost(RuntimeError):
    """The worker's lease expired or was taken over; its work must not commit."""


class RetryableError(RuntimeError):
    def __init__(self, message: str, code: str = "TRANSIENT"):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    organization_id: uuid.UUID
    job_type: str
    object_ref: uuid.UUID | None
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    lease_token: uuid.UUID


# -- producing work ----------------------------------------------------------


def enqueue(
    tx: TenantSession,
    job_type: str,
    *,
    object_ref: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
    dedupe_key: str | None = None,
    delay_seconds: float = 0,
    max_attempts: int = 5,
) -> Job:
    """Add a job in the caller's transaction. A repeated dedupe key returns the original."""
    if dedupe_key is not None:
        existing = tx.session.scalars(
            select(Job).where(
                Job.organization_id == tx.organization_id,
                Job.job_type == job_type,
                Job.dedupe_key == dedupe_key,
            )
        ).first()
        if existing is not None:
            return existing
    job = Job(
        organization_id=tx.organization_id,
        job_type=job_type,
        object_ref=object_ref,
        payload=to_jsonable(payload or {}),
        dedupe_key=dedupe_key,
        available_at=utcnow() + timedelta(seconds=delay_seconds),
        max_attempts=max_attempts,
    )
    tx.session.add(job)
    tx.session.flush()
    return job


def emit(
    tx: TenantSession,
    event_type: str,
    *,
    aggregate_id: uuid.UUID,
    aggregate_revision: int = 0,
    data: dict[str, Any] | None = None,
) -> OutboxEvent:
    event = OutboxEvent(
        organization_id=tx.organization_id,
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_revision=aggregate_revision,
        data=to_jsonable(data or {}),
    )
    tx.session.add(event)
    tx.session.flush()
    return event


# -- consuming work ----------------------------------------------------------


def claim(
    db: Database, *, lease_seconds: int = 60, job_types: list[str] | None = None
) -> ClaimedJob | None:
    now = utcnow()
    with db.system() as session:
        stmt = select(Job).where(Job.state == JobState.READY, Job.available_at <= now)
        if job_types:
            stmt = stmt.where(Job.job_type.in_(job_types))
        stmt = stmt.order_by(Job.available_at).limit(1).with_for_update(skip_locked=True)
        job = session.scalars(stmt).first()
        if job is None:
            return None
        job.state = JobState.RUNNING
        job.attempts += 1
        job.lease_token = uuid.uuid4()
        job.lease_until = now + timedelta(seconds=lease_seconds)
        return ClaimedJob(
            id=job.id,
            organization_id=job.organization_id,
            job_type=job.job_type,
            object_ref=job.object_ref,
            payload=dict(job.payload),
            attempts=job.attempts,
            max_attempts=job.max_attempts,
            lease_token=job.lease_token,
        )


def assert_lease(session: Session, job: ClaimedJob) -> None:
    """Lock the job row and confirm this worker still holds the lease."""
    current = session.scalars(select(Job).where(Job.id == job.id).with_for_update()).first()
    if (
        current is None
        or current.state != JobState.RUNNING
        or current.lease_token != job.lease_token
        or current.lease_until is None
        or current.lease_until < utcnow()
    ):
        raise LeaseLost(f"Lease lost for job {job.id}")


def complete(session: Session, job: ClaimedJob) -> None:
    """Mark the job done in ``session``'s transaction, fenced by the lease token."""
    assert_lease(session, job)
    session.execute(
        update(Job)
        .where(Job.id == job.id, Job.lease_token == job.lease_token)
        .values(state=JobState.SUCCEEDED, completed_at=utcnow(), lease_until=None)
    )


def backoff_seconds(attempt: int, *, base: float = 2.0, cap: float = 300.0) -> float:
    delay = min(cap, base * (2 ** (attempt - 1)))
    return delay / 2 + random.uniform(0, delay / 2)  # jitter in [delay/2, delay]


def fail(db: Database, job: ClaimedJob, *, code: str, message: str, retryable: bool) -> str:
    """Record a failure. Returns the resulting state."""
    with db.system() as session:
        current = session.scalars(select(Job).where(Job.id == job.id).with_for_update()).first()
        if current is None or current.lease_token != job.lease_token:
            return current.state if current else JobState.DEAD
        current.last_error_code = code[:80]
        current.last_error_message = redact(message)[:500]
        current.lease_token = None
        current.lease_until = None
        if retryable and current.attempts < current.max_attempts:
            current.state = JobState.READY
            current.available_at = utcnow() + timedelta(seconds=backoff_seconds(current.attempts))
        else:
            current.state = JobState.DEAD
        return current.state


def reap_expired(db: Database) -> int:
    """Return jobs whose lease expired to the queue (or DEAD when exhausted)."""
    now = utcnow()
    count = 0
    with db.system() as session:
        expired = session.scalars(
            select(Job)
            .where(Job.state == JobState.RUNNING, Job.lease_until < now)
            .with_for_update(skip_locked=True)
        ).all()
        for job in expired:
            job.lease_token = None
            job.lease_until = None
            job.last_error_code = "LEASE_EXPIRED"
            job.state = JobState.DEAD if job.attempts >= job.max_attempts else JobState.READY
            count += 1
    return count


def retry_dead(db: Database, organization_id: uuid.UUID, job_id: uuid.UUID) -> Job | None:
    """Operator action: give a DEAD job one more attempt."""
    with db.system() as session:
        job = session.scalars(
            select(Job)
            .where(Job.id == job_id, Job.organization_id == organization_id)
            .with_for_update()
        ).first()
        if job is None or job.state != JobState.DEAD:
            return job
        job.state = JobState.READY
        job.max_attempts = job.attempts + 1
        job.available_at = utcnow()
        return job
