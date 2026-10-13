from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.actions import proposals
from backend.actions.handlers import proposal_view
from backend.actions.models import ActionProposal
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import idempotency
from backend.runtime import Runtime

router = APIRouter(prefix="/v1", tags=["actions"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AmountIn(Strict):
    amount_minor: str = Field(pattern=r"^-?\d{1,19}$")
    currency: str = Field(min_length=3, max_length=3)


class ProposalIn(Strict):
    """Requested fields only. A client-supplied digest is rejected as unknown."""

    case_id: uuid.UUID
    expected_case_revision: int
    action_type: str = "PAYMENT"
    amount: AmountIn
    beneficiary_version_id: uuid.UUID
    purpose: str = Field(min_length=3, max_length=300)
    mode: str = "SIMULATED"
    source_references: list[str] = Field(default_factory=list, max_length=20)


class HaltIn(Strict):
    halted: bool
    reason: str = Field(min_length=3, max_length=1000)


@router.post("/action-proposals", status_code=201)
def create_proposal(
    body: ProposalIn,
    actor: Actor = Depends(require(Capability.PROPOSAL_CREATE)),
    rt: Runtime = Depends(get_runtime),
    idempotency_key: str | None = Header(default=None),
):
    def operation(tx):
        proposal = proposals.create_proposal(
            tx,
            actor,
            proposals.ProposalRequest(
                case_id=body.case_id,
                expected_case_revision=body.expected_case_revision,
                action_type=body.action_type,
                amount_minor=body.amount.amount_minor,
                currency=body.amount.currency,
                beneficiary_version_id=body.beneficiary_version_id,
                purpose=body.purpose,
                mode=body.mode,
                source_references=tuple(body.source_references),
            ),
        )
        return 201, proposal_view(tx, proposal)

    result = idempotency.run(
        rt.db,
        actor,
        route="POST /v1/action-proposals",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        operation=operation,
    )
    return JSONResponse(status_code=result.status, content=result.body)


@router.get("/action-proposals/{proposal_id}")
def get_proposal(
    proposal_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return proposal_view(tx, tx.get(ActionProposal, proposal_id))


@router.get("/actions/controls")
def get_controls(
    actor: Actor = Depends(require(Capability.CASE_READ)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        control = proposals.control_for(tx)
        return {
            "halted": bool(control and control.halted),
            "reason": control.reason if control else None,
            "changed_by": control.changed_by if control else None,
        }


@router.post("/actions/emergency-stop")
def emergency_stop(
    body: HaltIn,
    actor: Actor = Depends(require(Capability.ACTION_HALT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        control = proposals.set_halt(tx, actor, halted=body.halted, reason=body.reason)
        return {"halted": control.halted, "reason": control.reason}
