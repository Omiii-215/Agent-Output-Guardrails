from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select

from apps.api.deps import get_runtime, require
from backend.errors import Conflict, NotFound
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.runtime import Runtime

router = APIRouter(prefix="/v1/operations", tags=["operations"])


class JobOut(BaseModel):
    id: uuid.UUID
    job_type: str
    object_ref: uuid.UUID | None
    state: str
    attempts: int
    max_attempts: int
    available_at: datetime
    last_error_code: str | None
    last_error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    @classmethod
    def of(cls, job: jobs.Job) -> JobOut:
        return cls.model_validate(job, from_attributes=True)


@router.get("/jobs", response_model=list[JobOut])
def list_jobs(
    state: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    actor: Actor = Depends(require(Capability.OPERATIONS_READ)),
    rt: Runtime = Depends(get_runtime),
):
    # Job rows carry metadata only; scope explicitly to the caller's organization.
    with rt.db.system() as session:
        stmt = select(jobs.Job).where(jobs.Job.organization_id == actor.organization_id)
        if state:
            stmt = stmt.where(jobs.Job.state == state)
        rows = session.scalars(stmt.order_by(jobs.Job.created_at.desc()).limit(limit)).all()
        return [JobOut.of(j) for j in rows]


@router.post("/jobs/{job_id}/retry", response_model=JobOut)
def retry_job(
    job_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.OPERATIONS_READ)),
    rt: Runtime = Depends(get_runtime),
):
    job = jobs.retry_dead(rt.db, actor.organization_id, job_id)
    if job is None:
        raise NotFound("Job not found")
    if job.state != jobs.JobState.READY:
        raise Conflict("Only dead-lettered jobs can be retried", code="JOB_NOT_DEAD")
    return JobOut.of(job)
