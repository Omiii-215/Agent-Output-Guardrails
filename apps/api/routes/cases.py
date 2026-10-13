from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.cases import detail
from backend.cases import service as cases
from backend.cases.models import Case, CaseComment
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.modules.registry import MODULES
from backend.runtime import Runtime
from backend.telemetry.audit import AuditEvent

router = APIRouter(prefix="/v1", tags=["cases"])


class CaseOut(BaseModel):
    id: uuid.UUID
    module: str
    title: str
    status: str
    outcome: str | None
    subject_type: str | None
    subject_id: uuid.UUID | None
    owner_subject: str | None
    created_by: str
    revision: int
    due_at: datetime | None
    closed_reason: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, case: Case) -> CaseOut:
        return cls.model_validate(case, from_attributes=True)


class CommentOut(BaseModel):
    id: uuid.UUID
    author_subject: str
    body: str
    created_at: datetime

    @classmethod
    def of(cls, c: CaseComment) -> CommentOut:
        return cls.model_validate(c, from_attributes=True)


class AuditOut(BaseModel):
    id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    object_type: str
    object_id: uuid.UUID | None
    reason: str | None
    data: dict
    simulated: bool
    occurred_at: datetime
    trace_id: str | None

    @classmethod
    def of(cls, e: AuditEvent) -> AuditOut:
        return cls.model_validate(e, from_attributes=True)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssignIn(Strict):
    owner_subject: str = Field(min_length=3, max_length=200)
    expected_revision: int


class CloseIn(Strict):
    reason: str = Field(min_length=3, max_length=1000)
    expected_revision: int


class CommentIn(Strict):
    body: str = Field(min_length=1, max_length=4000)


@router.get("/modules")
def list_modules():
    return [
        {
            "code": m.code.value,
            "number": m.number,
            "name": m.name,
            "stage": m.stage,
            "enabled": m.enabled,
            "simulation_only": m.simulation_only,
            "summary": m.summary,
            "activation_gate": m.activation_gate,
        }
        for m in MODULES
    ]


@router.get("/cases")
def list_cases(
    status: list[str] | None = Query(default=None),
    module: str | None = None,
    owner: str | None = None,
    open_only: bool = False,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        rows, next_cursor = cases.queue(
            tx,
            status=status,
            module=module,
            owner=owner,
            open_only=open_only,
            cursor=cursor,
            limit=limit,
        )
        return {"items": [CaseOut.of(c) for c in rows], "next_cursor": next_cursor}


@router.get("/cases/{case_id}/comments", response_model=list[CommentOut])
def list_comments(
    case_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return [CommentOut.of(c) for c in cases.comments(tx, case_id)]


@router.post("/cases/{case_id}/comments", response_model=CommentOut, status_code=201)
def add_comment(
    case_id: uuid.UUID,
    body: CommentIn,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return CommentOut.of(cases.add_comment(tx, actor, case_id, body.body))


@router.post("/cases/{case_id}/assign", response_model=CaseOut)
def assign_case(
    case_id: uuid.UUID,
    body: AssignIn,
    actor: Actor = Depends(require(Capability.CASE_WRITE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return CaseOut.of(
            cases.assign(tx, actor, case_id, body.owner_subject, body.expected_revision)
        )


@router.post("/cases/{case_id}/close", response_model=CaseOut)
def close_case(
    case_id: uuid.UUID,
    body: CloseIn,
    actor: Actor = Depends(require(Capability.CASE_WRITE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return CaseOut.of(cases.close(tx, actor, case_id, body.reason, body.expected_revision))


@router.get("/cases/{case_id}")
def get_case(
    case_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        case = tx.get(Case, case_id)
        section = detail.compose(tx, case)
        return {"case": CaseOut.of(case), **section.data}


@router.get("/cases/{case_id}/history", response_model=list[AuditOut])
def case_history(
    case_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        case = tx.get(Case, case_id)
        related = detail.compose(tx, case).related_ids
        return [AuditOut.of(e) for e in cases.history(tx, case_id, related)]


@router.get("/modules/{code}")
def module_detail(code: str):
    from backend.errors import NotFound
    from backend.modules.gated import CONTRACTS
    from backend.modules.registry import module_info

    try:
        info = module_info(code)
    except ValueError:
        raise NotFound("Unknown module") from None
    contract = CONTRACTS.get(code)
    return {
        "code": info.code.value,
        "name": info.name,
        "stage": info.stage,
        "enabled": info.enabled,
        "simulation_only": info.simulation_only,
        "summary": info.summary,
        "activation_gate": info.activation_gate,
        "contract": (
            {
                "input_schema": contract.input_model.model_json_schema(),
                "required_evidence": list(contract.required_evidence),
                "output": contract.output,
                "boundary": contract.boundary,
            }
            if contract
            else None
        ),
    }
