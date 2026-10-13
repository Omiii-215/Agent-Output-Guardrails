"""Controlled execution (LLD §7–9, diagram 07).

Intent → RESERVED: one short transaction locks intent, proposal and spend
buckets in a fixed order, recomputes the digest, re-validates approvals,
controls and source freshness, then reserves the amount.

RESERVED → SUBMITTING: the execution claim is the authorization boundary.
The stable provider key and request digest are persisted before the network
call, which happens outside any transaction.

Timeouts become UNKNOWN: the reservation is held and status reconciliation
decides. No path issues a fresh transfer for the same intent.
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.adapters.payments.simulator import FrozenAction, PaymentAdapter, ProviderTimeout
from backend.approvals import service as approvals
from backend.approvals.models import ApprovalRequest, RequestState
from backend.cases import detail, hooks
from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.domain.canonical import digest
from backend.domain.clock import utcnow
from backend.errors import Conflict
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.telemetry import audit

from . import proposals, sources
from .models import (
    ActionAttempt,
    ActionIntent,
    ActionProposal,
    IntentState,
    ProposalState,
    SpendBucket,
    SpendReservation,
)
from .spend import lock_buckets

RESERVE_JOB = "actions.reserve"
EXECUTE_JOB = "actions.execute"
RECONCILE_JOB = "actions.reconcile"
WEBHOOK_JOB = "actions.webhook"


def _set(tx: TenantSession, intent: ActionIntent, state: str, reason: str | None = None) -> None:
    previous = intent.state
    intent.state, intent.state_reason = state, reason
    intent.revision += 1
    intent.updated_at = utcnow()
    audit.record(
        tx,
        "intent." + state.lower(),
        object_type="action_intent",
        object_id=intent.id,
        reason=reason,
        data={"from": previous, "proposal_id": intent.proposal_id, "case_id": intent.case_id},
        simulated=intent.mode == "SIMULATED",
    )


# -- intent creation ------------------------------------------------------------------


def create_intent(
    tx: TenantSession,
    actor: Actor,
    *,
    proposal_id: uuid.UUID,
    approval_request_id: uuid.UUID,
    provider: str,
) -> ActionIntent:
    """Create the single execution intent for an approved proposal.

    No action fields are accepted: amount, payee and mode come from the frozen
    proposal. Repeating the call returns the existing intent.
    """
    actor.require(Capability.INTENT_CREATE)
    proposal = tx.get(ActionProposal, proposal_id, for_update=True)
    existing = tx.first(tx.select(ActionIntent).where(ActionIntent.proposal_id == proposal.id))
    if existing is not None:
        return existing
    request = tx.get(ApprovalRequest, approval_request_id, for_update=True)
    if request.proposal_id != proposal.id:
        raise Conflict("Approval belongs to another proposal", code="APPROVAL_MISMATCH")
    if proposal.state != ProposalState.APPROVED or request.state != RequestState.APPROVED:
        raise Conflict("Proposal is not approved", code="NOT_APPROVED")
    if approvals.effective_state(request) == RequestState.EXPIRED:
        raise Conflict("The approval expired", code="APPROVAL_EXPIRED")
    _check_integrity(proposal, request)
    if len(approvals.valid_approvals(tx, request)) < request.required_count:
        raise Conflict("Approver authority changed; re-approval needed", code="APPROVER_REVOKED")

    intent_id = uuid.uuid4()
    intent = tx.add(
        ActionIntent(
            id=intent_id,
            proposal_id=proposal.id,
            approval_request_id=request.id,
            case_id=proposal.case_id,
            action_digest=proposal.digest,
            mode=proposal.mode,
            amount_minor=proposal.amount_minor,
            currency=proposal.currency,
            provider=provider,
            provider_idempotency_key=f"fg-{tx.organization_id.hex[:8]}-{intent_id.hex}",
            created_by=actor.subject,
        )
    )
    tx.flush()
    proposals.set_state(tx, proposal, ProposalState.INTENT_CREATED, "Execution intent created")
    audit.record(
        tx,
        "intent.created",
        object_type="action_intent",
        object_id=intent.id,
        data={"proposal_id": proposal.id, "digest": intent.action_digest},
        simulated=intent.mode == "SIMULATED",
    )
    jobs.enqueue(tx, RESERVE_JOB, object_ref=intent.id, dedupe_key=str(intent.id))
    return intent


def _check_integrity(proposal: ActionProposal, request: ApprovalRequest) -> None:
    recomputed = digest(proposal.canonical_payload)
    if not (recomputed == proposal.digest == request.action_digest):
        raise Conflict("Payload digest mismatch", code="DIGEST_MISMATCH")


# -- reservation ----------------------------------------------------------------------


def reserve(tx: TenantSession, intent_id: uuid.UUID, created_by: str) -> None:
    intent = tx.get(ActionIntent, intent_id, for_update=True)
    if intent.state != IntentState.CREATED:
        return
    proposal = tx.get(ActionProposal, intent.proposal_id, for_update=True)
    request = tx.get(ApprovalRequest, intent.approval_request_id)
    case = cases.get_for_update(tx, intent.case_id)

    problem = _recheck(tx, intent, proposal, request, case, created_by)
    policy = policies.document_of(policies.active_policy(tx, proposals.POLICY_CODE))
    buckets = lock_buckets(tx, policy, intent.currency) if problem is None else []
    if problem is None and not buckets:
        problem = "NO_SPEND_LIMIT"
    for bucket in buckets:
        if problem is None and intent.amount_minor > (
            bucket.limit_minor - bucket.committed_minor - bucket.reserved_minor
        ):
            problem = "SPEND_LIMIT_EXCEEDED"
    if problem is not None:
        _invalidate_unclaimed(tx, intent, proposal, problem)
        return

    for bucket in buckets:
        bucket.reserved_minor += intent.amount_minor
        tx.add(
            SpendReservation(
                bucket_id=bucket.id, intent_id=intent.id, amount_minor=intent.amount_minor
            )
        )
    _set(tx, intent, IntentState.RESERVED, "Preflight passed; amount reserved")
    if case.status == CaseStatus.READY_FOR_ACTION:
        cases.transition(tx, case, CaseStatus.ACTION_PENDING, reason="Execution reserved")
    jobs.enqueue(tx, EXECUTE_JOB, object_ref=intent.id, dedupe_key=str(intent.id))


def _recheck(
    tx: TenantSession,
    intent: ActionIntent,
    proposal: ActionProposal,
    request: ApprovalRequest,
    case: Case,
    created_by: str,
) -> str | None:
    """Re-validate everything dynamic immediately before reserving."""
    try:
        _check_integrity(proposal, request)
    except Conflict:
        return "DIGEST_MISMATCH"
    if intent.action_digest != proposal.digest:
        return "DIGEST_MISMATCH"
    if approvals.effective_state(request) != RequestState.APPROVED:
        return "APPROVAL_NOT_VALID"
    if len(approvals.valid_approvals(tx, request)) < request.required_count:
        return "APPROVER_REVOKED"
    if case.status != CaseStatus.READY_FOR_ACTION:
        return f"CASE_{case.status}"
    inputs, revisions = proposals.build_preflight_inputs(tx, proposal)
    # The intent's own proposal is not a duplicate of itself.
    inputs["duplicates"]["other_active_proposals"] = []
    evaluation = policies.record_evaluation(
        tx,
        case=case,
        kind="EXECUTION",
        inputs=inputs,
        source_revision_map=revisions,
        policy=policies.active_policy(tx, proposals.POLICY_CODE),
        created_by=created_by,
        proposal_id=proposal.id,
    )
    if evaluation.outcome != "PASS":
        failing = [
            v.finding.reason_code
            for v in policies.findings_for(tx, evaluation.id)
            if v.finding.effect
        ]
        return "PREFLIGHT_" + evaluation.outcome + (":" + ",".join(failing) if failing else "")
    return None


def _invalidate_unclaimed(
    tx: TenantSession, intent: ActionIntent, proposal: ActionProposal, reason: str
) -> None:
    """Invalidate an intent that was never claimed for submission."""
    _release(tx, intent)
    _set(tx, intent, IntentState.INVALIDATED, reason)
    proposals.set_state(tx, proposal, ProposalState.STALE, f"Execution invalidated: {reason}")
    case = tx.get(Case, intent.case_id)
    if case.status in (CaseStatus.READY_FOR_ACTION, CaseStatus.ACTION_PENDING):
        cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)


def _reservations(tx: TenantSession, intent: ActionIntent) -> list[SpendReservation]:
    return list(
        tx.scalars(
            tx.select(SpendReservation)
            .where(SpendReservation.intent_id == intent.id)
            .with_for_update()
        )
    )


def _release(tx: TenantSession, intent: ActionIntent) -> None:
    for r in _reservations(tx, intent):
        if r.state == "ACTIVE":
            bucket = tx.get(SpendBucket, r.bucket_id, for_update=True)
            bucket.reserved_minor -= r.amount_minor
            r.state, r.updated_at = "RELEASED", utcnow()


def _commit_spend(tx: TenantSession, intent: ActionIntent) -> None:
    for r in _reservations(tx, intent):
        if r.state == "ACTIVE":
            bucket = tx.get(SpendBucket, r.bucket_id, for_update=True)
            bucket.reserved_minor -= r.amount_minor
            bucket.committed_minor += r.amount_minor
            r.state, r.updated_at = "COMMITTED", utcnow()


def _uncommit_spend(tx: TenantSession, intent: ActionIntent) -> None:
    for r in _reservations(tx, intent):
        bucket = tx.get(SpendBucket, r.bucket_id, for_update=True)
        if r.state == "COMMITTED":
            bucket.committed_minor -= r.amount_minor
        elif r.state == "ACTIVE":
            bucket.reserved_minor -= r.amount_minor
        r.state, r.updated_at = "RELEASED", utcnow()


# -- claim and submission --------------------------------------------------------------


def claim(tx: TenantSession, intent_id: uuid.UUID) -> tuple[ActionIntent, FrozenAction] | None:
    """Claim a RESERVED intent for submission. Returns None when nothing to send."""
    intent = tx.get(ActionIntent, intent_id, for_update=True)
    if intent.state == IntentState.SUBMITTING:
        # A previous worker claimed it and may have called the provider.
        _set(tx, intent, IntentState.UNKNOWN, "Claimed submission without a recorded result")
        jobs.enqueue(tx, RECONCILE_JOB, object_ref=intent.id, dedupe_key=f"{intent.id}:claim")
        return None
    if intent.state != IntentState.RESERVED:
        return None
    control = proposals.control_for(tx)
    if control is not None and control.halted:
        proposal = tx.get(ActionProposal, intent.proposal_id, for_update=True)
        _invalidate_unclaimed(tx, intent, proposal, "EMERGENCY_STOP")
        return None
    proposal = tx.get(ActionProposal, intent.proposal_id)
    if digest(proposal.canonical_payload) != intent.action_digest:
        _invalidate_unclaimed(tx, intent, proposal, "DIGEST_MISMATCH")
        return None
    intent.attempts += 1
    intent.claimed_at = utcnow()
    _set(tx, intent, IntentState.SUBMITTING, "Execution claimed")
    payload = proposal.canonical_payload
    action = FrozenAction(
        organization_id=tx.organization_id,
        amount_minor=intent.amount_minor,
        currency=intent.currency,
        beneficiary_fingerprint=payload["beneficiary"]["account_fingerprint"],
        reference=str(intent.id),
    )
    return intent, action


def _attempt(
    tx: TenantSession, intent: ActionIntent, kind: str, outcome: str, ref: str | None, code: str
) -> None:
    tx.add(
        ActionAttempt(
            intent_id=intent.id,
            attempt_number=intent.attempts,
            kind=kind,
            provider_idempotency_key=intent.provider_idempotency_key,
            request_digest=intent.action_digest,
            outcome=outcome,
            provider_reference=ref,
            response_code=code,
        )
    )


def record_submission(
    tx: TenantSession, intent_id: uuid.UUID, result: Any, *, timed_out: bool
) -> None:
    intent = tx.get(ActionIntent, intent_id, for_update=True)
    if intent.state != IntentState.SUBMITTING:
        return
    if timed_out:
        _attempt(tx, intent, "SUBMIT", "UNKNOWN", None, "TIMEOUT")
        _set(tx, intent, IntentState.UNKNOWN, "Provider did not answer; reservation held")
        jobs.enqueue(
            tx,
            RECONCILE_JOB,
            object_ref=intent.id,
            dedupe_key=f"{intent.id}:{intent.attempts}",
            delay_seconds=0,
        )
        return
    _attempt(tx, intent, "SUBMIT", result.outcome, result.provider_reference, result.code)
    intent.provider_reference = result.provider_reference
    if result.outcome == "ACCEPTED":
        _accept(tx, intent)
    else:
        _fail(tx, intent, f"Provider rejected: {result.code}")


def _accept(tx: TenantSession, intent: ActionIntent) -> None:
    _commit_spend(tx, intent)
    _set(tx, intent, IntentState.ACCEPTED, "Provider accepted; awaiting settlement")


def _fail(tx: TenantSession, intent: ActionIntent, reason: str) -> None:
    _uncommit_spend(tx, intent)
    _set(tx, intent, IntentState.FAILED, reason)
    case = cases.get_for_update(tx, intent.case_id)
    if case.status == CaseStatus.ACTION_PENDING:
        cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)


def submit(adapter: PaymentAdapter, intent: ActionIntent, action: FrozenAction):
    try:
        return adapter.submit(action, intent.provider_idempotency_key), False
    except ProviderTimeout:
        return None, True


# -- reconciliation ----------------------------------------------------------------------


def apply_status(tx: TenantSession, intent_id: uuid.UUID, status: Any) -> None:
    """Resolve an UNKNOWN intent from the provider's authoritative status."""
    intent = tx.get(ActionIntent, intent_id, for_update=True)
    if intent.state != IntentState.UNKNOWN:
        return
    _attempt(tx, intent, "STATUS", status.state, status.provider_reference, "STATUS")
    if status.state in ("ACCEPTED", "SETTLED"):
        intent.provider_reference = status.provider_reference
        _accept(tx, intent)
        if status.state == "SETTLED":
            _settle(tx, intent)
    elif status.state in ("NOT_FOUND", "FAILED"):
        _fail(tx, intent, "Provider confirmed no successful transfer")


def _settle(tx: TenantSession, intent: ActionIntent) -> None:
    _set(tx, intent, IntentState.SETTLED, "Settlement confirmed")
    case = cases.get_for_update(tx, intent.case_id)
    sources.on_settled(
        tx,
        case,
        {
            "intent_id": intent.id,
            "amount_minor": intent.amount_minor,
            "currency": intent.currency,
            "provider_reference": intent.provider_reference,
            "mode": intent.mode,
        },
    )
    if case.status == CaseStatus.ACTION_PENDING:
        cases.transition(tx, case, CaseStatus.RESOLVED, reason="Payment settled")


def apply_event(tx: TenantSession, event: dict[str, Any]) -> str:
    """Process a verified provider event. Old or repeated events never regress state."""
    intent = tx.first(
        tx.select(ActionIntent)
        .where(ActionIntent.provider_idempotency_key == event["idempotency_key"])
        .with_for_update()
    )
    if intent is None:
        return "UNMATCHED"
    kind = event["type"]
    _attempt(tx, intent, "WEBHOOK", kind, event.get("provider_reference"), event["event_id"][:60])
    if kind == "transfer.settled":
        if intent.state == IntentState.UNKNOWN:
            intent.provider_reference = event.get("provider_reference")
            _accept(tx, intent)
        if intent.state == IntentState.ACCEPTED:
            _settle(tx, intent)
            return "SETTLED"
    elif kind == "transfer.failed":
        if intent.state in (IntentState.ACCEPTED, IntentState.UNKNOWN):
            _fail(tx, intent, "Provider reported failure")
            return "FAILED"
    elif kind == "transfer.reversed" and intent.state == IntentState.SETTLED:
        _uncommit_spend(tx, intent)
        _set(tx, intent, IntentState.REVERSED, "Provider confirmed reversal")
        return "REVERSED"
    return "IGNORED"


# -- invalidation on material change ---------------------------------------------------------


@hooks.on_inputs_changed
def _inputs_changed(tx: TenantSession, case: Case, reason: str) -> None:
    for intent in tx.scalars(
        tx.select(ActionIntent).where(ActionIntent.case_id == case.id).with_for_update()
    ):
        if intent.state in (IntentState.CREATED, IntentState.RESERVED):
            proposal = tx.get(ActionProposal, intent.proposal_id, for_update=True)
            _release(tx, intent)
            _set(tx, intent, IntentState.INVALIDATED, f"Input changed before submission: {reason}")
            proposals.set_state(tx, proposal, ProposalState.STALE, reason)
            if case.status == CaseStatus.ACTION_PENDING:
                cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)
        elif intent.state in (IntentState.SUBMITTING, IntentState.ACCEPTED, IntentState.UNKNOWN):
            # Already claimed: a change cannot recall money. Make it visible.
            audit.record(
                tx,
                "intent.changed_after_submission",
                object_type="action_intent",
                object_id=intent.id,
                reason=reason,
                simulated=intent.mode == "SIMULATED",
            )


def view(tx: TenantSession, intent: ActionIntent) -> dict[str, Any]:
    request = tx.get(ApprovalRequest, intent.approval_request_id)
    attempts = tx.scalars(
        tx.select(ActionAttempt)
        .where(ActionAttempt.intent_id == intent.id)
        .order_by(ActionAttempt.created_at)
    )
    reservations = tx.scalars(
        tx.select(SpendReservation).where(SpendReservation.intent_id == intent.id)
    )
    return {
        "id": intent.id,
        "proposal_id": intent.proposal_id,
        "case_id": intent.case_id,
        "mode": intent.mode,
        "simulated": intent.mode == "SIMULATED",
        "action_digest": intent.action_digest,
        "amount_minor": str(intent.amount_minor),
        "currency": intent.currency,
        "approval": {"request_id": request.id, "state": approvals.effective_state(request)},
        "execution": {
            "state": intent.state,
            "reason": intent.state_reason,
            "attempts": intent.attempts,
            "claimed_at": intent.claimed_at,
        },
        "provider": {
            "name": intent.provider,
            "idempotency_key": intent.provider_idempotency_key,
            "reference": intent.provider_reference,
            "history": [
                {
                    "kind": a.kind,
                    "outcome": a.outcome,
                    "code": a.response_code,
                    "at": a.created_at,
                }
                for a in attempts
            ],
        },
        "reservation": [
            {"amount_minor": str(r.amount_minor), "state": r.state} for r in reservations
        ],
        "revision": intent.revision,
    }


def intents_section(tx: TenantSession, case: Case) -> detail.DetailSection:
    intents = tx.scalars(
        tx.select(ActionIntent)
        .where(ActionIntent.case_id == case.id)
        .order_by(ActionIntent.created_at.desc())
    )
    proposal_ids = [
        p.id for p in tx.scalars(tx.select(ActionProposal).where(ActionProposal.case_id == case.id))
    ]
    requests = tx.scalars(
        tx.select(ApprovalRequest).where(ApprovalRequest.proposal_id.in_(proposal_ids))
    )
    return detail.DetailSection(
        data={"intents": [view(tx, i) for i in intents]},
        related_ids=[i.id for i in intents] + [r.id for r in requests],
    )


detail.register("invoices", intents_section)
