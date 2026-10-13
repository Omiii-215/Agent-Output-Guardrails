from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.actions.handlers import proposal_view
from backend.actions.models import ActionProposal
from backend.approvals import service as approvals
from backend.approvals.models import ApprovalRequest
from backend.cases.models import Case
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import idempotency
from backend.persistence.database import TenantSession
from backend.runtime import Runtime

router = APIRouter(prefix="/v1", tags=["approvals"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RequestIn(Strict):
    proposal_id: uuid.UUID


class DecisionIn(Strict):
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    reason: str = Field(min_length=3, max_length=1000)
    expected_revision: int


def _request_out(tx: TenantSession, request: ApprovalRequest) -> dict:
    proposal = tx.get(ActionProposal, request.proposal_id)
    case = tx.get(Case, proposal.case_id)
    return {
        "id": str(request.id),
        "state": approvals.effective_state(request),
        "revision": request.revision,
        "required_count": request.required_count,
        "approved_count": len(approvals.valid_approvals(tx, request)),
        "expires_at": request.expires_at.isoformat(),
        "action_digest": request.action_digest,
        "requested_by": request.requested_by,
        "case": {"id": str(case.id), "title": case.title},
        "proposal": proposal_view(tx, proposal),
    }


@router.post("/approval-requests", status_code=201)
def create_request(
    body: RequestIn,
    actor: Actor = Depends(require(Capability.APPROVAL_REQUEST)),
    rt: Runtime = Depends(get_runtime),
    idempotency_key: str | None = Header(default=None),
):
    def operation(tx):
        return 201, _request_out(tx, approvals.create_request(tx, actor, body.proposal_id))

    result = idempotency.run(
        rt.db,
        actor,
        route="POST /v1/approval-requests",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        operation=operation,
    )
    return JSONResponse(status_code=result.status, content=result.body)


@router.get("/approval-requests")
def list_requests(
    state: str | None = "PENDING",
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        stmt = tx.select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
        if state:
            stmt = stmt.where(ApprovalRequest.state == state)
        return [_request_out(tx, r) for r in tx.scalars(stmt.limit(200))]


@router.get("/approval-requests/{request_id}")
def get_request(
    request_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _request_out(tx, tx.get(ApprovalRequest, request_id))


@router.post("/approval-requests/{request_id}/decisions", status_code=201)
def decide(
    request_id: uuid.UUID,
    body: DecisionIn,
    actor: Actor = Depends(require(Capability.APPROVAL_DECIDE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        request = approvals.decide(
            tx,
            actor,
            request_id,
            decision=body.decision,
            reason=body.reason,
            expected_revision=body.expected_revision,
        )
        return _request_out(tx, request)
