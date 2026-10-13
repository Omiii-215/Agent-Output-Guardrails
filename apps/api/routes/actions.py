from __future__ import annotations

import hashlib
import json
import uuid

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from apps.api.deps import get_runtime, require, tenant_tx
from backend.actions import execution, proposals
from backend.actions.handlers import proposal_view
from backend.actions.models import ActionIntent, ActionProposal, WebhookReceipt
from backend.adapters.payments.simulator import encode_event, verify_signature
from backend.errors import InvalidInput, NotFound, Unauthenticated
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import idempotency, jobs
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


class IntentIn(Strict):
    """Only references. Amount, payee and mode always come from the frozen proposal."""

    proposal_id: uuid.UUID
    approval_request_id: uuid.UUID


class AdvanceIn(Strict):
    state: str = Field(pattern="^(SETTLED|FAILED|REVERSED)$")


@router.post("/action-intents", status_code=202)
def create_intent(
    body: IntentIn,
    actor: Actor = Depends(require(Capability.INTENT_CREATE)),
    rt: Runtime = Depends(get_runtime),
    idempotency_key: str | None = Header(default=None),
):
    def operation(tx):
        intent = execution.create_intent(
            tx,
            actor,
            proposal_id=body.proposal_id,
            approval_request_id=body.approval_request_id,
            provider=rt.payments.name,
        )
        return 202, execution.view(tx, intent)

    result = idempotency.run(
        rt.db,
        actor,
        route="POST /v1/action-intents",
        key=idempotency_key,
        body=body.model_dump(mode="json"),
        operation=operation,
    )
    return JSONResponse(status_code=result.status, content=result.body)


@router.get("/action-intents/{intent_id}")
def get_intent(
    intent_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return execution.view(tx, tx.get(ActionIntent, intent_id))


MAX_WEBHOOK_BYTES = 64 * 1024


def receive_webhook(rt: Runtime, body: bytes, signature: str | None) -> dict:
    """Verify the raw body first, persist a unique receipt, process asynchronously."""
    if len(body) > MAX_WEBHOOK_BYTES:
        raise InvalidInput("Webhook payload too large", code="PAYLOAD_TOO_LARGE")
    if not verify_signature(rt.settings.simulator_webhook_secret, body, signature):
        raise Unauthenticated("Invalid webhook signature", code="INVALID_SIGNATURE")
    try:
        event = json.loads(body)
        org = uuid.UUID(event["organization_id"])
        event_id = str(event["event_id"])[:100]
        if not isinstance(event.get("idempotency_key"), str) or "type" not in event:
            raise KeyError("idempotency_key/type")
    except (ValueError, KeyError, TypeError):
        raise InvalidInput("Malformed event", code="MALFORMED_EVENT") from None
    try:
        with rt.db.tenant(org) as tx:
            receipt = tx.add(
                WebhookReceipt(
                    connector="simulator",
                    provider_event_id=event_id,
                    payload=event,
                    payload_hash="sha256:" + hashlib.sha256(body).hexdigest(),
                )
            )
            tx.flush()
            jobs.enqueue(
                tx, execution.WEBHOOK_JOB, payload={"receipt_id": receipt.id}, dedupe_key=event_id
            )
    except IntegrityError:
        return {"status": "duplicate"}
    return {"status": "accepted"}


@router.post("/webhooks/simulator")
async def simulator_webhook(request: Request, rt: Runtime = Depends(get_runtime)):
    body = await request.body()
    return receive_webhook(rt, body, request.headers.get("x-simulator-signature"))


@router.post("/simulator/intents/{intent_id}/advance")
def advance_simulated_transfer(
    intent_id: uuid.UUID,
    body: AdvanceIn,
    actor: Actor = Depends(require(Capability.OPERATIONS_READ)),
    rt: Runtime = Depends(get_runtime),
):
    """Development console: make the simulated provider settle/fail/reverse a transfer
    and deliver the signed webhook through the normal ingestion path."""
    if rt.settings.env not in ("development", "test"):
        raise NotFound("Not found")
    with tenant_tx(rt.db, actor) as tx:
        intent = tx.get(ActionIntent, intent_id)
        key = intent.provider_idempotency_key
    event = rt.payments.advance(actor.organization_id, key, body.state)
    raw = encode_event(event)
    return receive_webhook(rt, raw, rt.payments.sign(raw))
