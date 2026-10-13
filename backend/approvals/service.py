"""Payload-bound approvals with independent reviewers (LLD §8, story P-04).

* The request is created from a proposal ID; the server selects the eligible
  action evaluation and copies the proposal digest.
* Reviewers approve that exact digest. The maker (and requester) cannot
  approve where independent approval is required; service accounts never
  approve; the reviewer's authority limit must cover the amount.
* Expiry, material changes, policy changes and revoked authority make the
  approval unusable; the proposal must be re-proposed and re-approved.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from backend.actions import handlers as action_handlers
from backend.actions import proposals
from backend.actions.models import ActionProposal, ProposalState
from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.domain.canonical import digest
from backend.domain.clock import ensure_aware, utcnow
from backend.errors import Conflict, Forbidden, InvalidInput
from backend.identity.actor import Actor
from backend.identity.models import Membership
from backend.identity.roles import Capability
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.policies.models import Evaluation
from backend.telemetry import audit

from .models import ApprovalDecision, ApprovalRequest, RequestState


def _set(tx: TenantSession, request: ApprovalRequest, state: str, reason: str | None) -> None:
    previous = request.state
    request.state, request.state_reason = state, reason
    request.revision += 1
    request.updated_at = utcnow()
    audit.record(
        tx,
        "approval.request_" + state.lower(),
        object_type="approval_request",
        object_id=request.id,
        reason=reason,
        data={"from": previous, "proposal_id": request.proposal_id},
    )


def create_request(tx: TenantSession, actor: Actor, proposal_id: uuid.UUID) -> ApprovalRequest:
    actor.require(Capability.APPROVAL_REQUEST)
    proposal = tx.get(ActionProposal, proposal_id, for_update=True)
    if proposal.state == ProposalState.PREFLIGHT_PENDING:
        raise Conflict("Preflight is still running", code="PREFLIGHT_PENDING")
    if proposal.state == ProposalState.AWAITING_APPROVAL:
        raise Conflict("An approval request is already pending", code="REQUEST_EXISTS")
    if proposal.state != ProposalState.READY_FOR_APPROVAL:
        raise Conflict(
            f"Proposal is {proposal.state}; it is not eligible for approval",
            code="PROPOSAL_NOT_ELIGIBLE",
        )
    evaluation = proposals.latest_action_evaluation(tx, proposal)
    if evaluation is None or evaluation.outcome != "PASS":
        raise Conflict("No eligible preflight evaluation", code="PREFLIGHT_UNRESOLVED")
    if digest(proposal.canonical_payload) != proposal.digest:
        raise Conflict("Proposal payload failed its integrity check", code="DIGEST_MISMATCH")

    policy = policies.get_policy(tx, evaluation.policy_version_id)
    config = policies.document_of(policy).approval
    if config is None:
        raise Conflict("Payment policy has no approval settings", code="NO_APPROVAL_POLICY")
    required = config.approvals_required(proposal.amount_minor)
    request = tx.add(
        ApprovalRequest(
            proposal_id=proposal.id,
            evaluation_id=evaluation.id,
            action_digest=proposal.digest,
            policy_version_id=policy.id,
            amount_minor=proposal.amount_minor,
            currency=proposal.currency,
            requirements=policies.freeze_inputs(config.model_dump()),
            required_count=required,
            expires_at=utcnow() + timedelta(minutes=config.expiry_minutes),
            requested_by=actor.subject,
        )
    )
    tx.flush()
    proposals.set_state(tx, proposal, ProposalState.AWAITING_APPROVAL, "Approval requested")
    audit.record(
        tx,
        "approval.requested",
        object_type="approval_request",
        object_id=request.id,
        data={
            "proposal_id": proposal.id,
            "digest": proposal.digest,
            "required_count": required,
            "expires_at": request.expires_at,
        },
        simulated=proposal.mode == "SIMULATED",
    )
    return request


def _expired(request: ApprovalRequest) -> bool:
    return ensure_aware(request.expires_at) <= utcnow()


def effective_state(request: ApprovalRequest) -> str:
    """Pending or approved requests past their expiry are no longer usable."""
    if request.state in (RequestState.PENDING, RequestState.APPROVED) and _expired(request):
        return RequestState.EXPIRED
    return request.state


def decide(
    tx: TenantSession,
    actor: Actor,
    request_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    expected_revision: int,
) -> ApprovalRequest:
    actor.require(Capability.APPROVAL_DECIDE)
    if not actor.is_human:
        raise Forbidden("Only people can approve financial actions", code="HUMAN_REQUIRED")
    if decision not in ("APPROVE", "REJECT"):
        raise InvalidInput("Decision must be APPROVE or REJECT")
    request = tx.get(ApprovalRequest, request_id, for_update=True)
    proposal = tx.get(ActionProposal, request.proposal_id, for_update=True)
    if request.revision != expected_revision:
        raise Conflict("The request changed since you loaded it", code="STALE_REVISION")
    if request.state != RequestState.PENDING:
        raise Conflict(f"Request is {request.state}", code="REQUEST_NOT_PENDING")
    if _expired(request):
        # Nothing is written: the caller must re-propose. Views report it as expired.
        raise Conflict("The approval request expired", code="APPROVAL_EXPIRED")
    if (
        proposal.state != ProposalState.AWAITING_APPROVAL
        or proposal.digest != request.action_digest
    ):
        raise Conflict("The proposal no longer matches this request", code="PROPOSAL_CHANGED")
    if digest(proposal.canonical_payload) != request.action_digest:
        raise Conflict("Proposal payload failed its integrity check", code="DIGEST_MISMATCH")

    requirements = request.requirements
    if not requirements.get("maker_can_approve") and actor.subject in (
        proposal.maker_subject,
        request.requested_by,
    ):
        raise Forbidden("You cannot approve your own request", code="SELF_APPROVAL")
    if requirements["required_role"] not in actor.roles:
        raise Forbidden("Approver role required", code="ROLE_REQUIRED")
    if decision == "APPROVE" and (
        actor.approval_limit_minor is None or actor.approval_limit_minor < request.amount_minor
    ):
        raise Forbidden("Amount exceeds your approval authority", code="AUTHORITY_LIMIT")
    prior = tx.first(
        tx.select(ApprovalDecision).where(
            ApprovalDecision.request_id == request.id,
            ApprovalDecision.actor_subject == actor.subject,
        )
    )
    if prior is not None:
        raise Conflict("You already decided this request", code="ALREADY_DECIDED")

    tx.add(
        ApprovalDecision(
            request_id=request.id,
            actor_subject=actor.subject,
            membership_id=actor.principal_id,
            roles_at_decision=list(actor.roles),
            authorization_revision=actor.authorization_revision,
            decision=decision,
            reason=reason,
            action_digest=request.action_digest,
        )
    )
    tx.flush()
    audit.record(
        tx,
        f"approval.{decision.lower()}d",
        object_type="approval_request",
        object_id=request.id,
        reason=reason,
        data={"proposal_id": proposal.id, "digest": request.action_digest},
        simulated=proposal.mode == "SIMULATED",
    )
    case = cases.get_for_update(tx, proposal.case_id)
    if decision == "REJECT":
        _set(tx, request, RequestState.REJECTED, reason)
        proposals.set_state(tx, proposal, ProposalState.REJECTED, reason)
        return request
    request.revision += 1
    if len(valid_approvals(tx, request)) >= request.required_count:
        _set(tx, request, RequestState.APPROVED, "Required approvals complete")
        proposals.set_state(tx, proposal, ProposalState.APPROVED, "Required approvals complete")
        if case.status == CaseStatus.IN_REVIEW:
            cases.transition(tx, case, CaseStatus.READY_FOR_ACTION, reason="Payment approved")
    return request


def valid_approvals(tx: TenantSession, request: ApprovalRequest) -> list[ApprovalDecision]:
    """Approvals whose reviewer still holds an active membership with the role."""
    decisions = tx.scalars(
        tx.select(ApprovalDecision).where(
            ApprovalDecision.request_id == request.id,
            ApprovalDecision.decision == "APPROVE",
            ApprovalDecision.action_digest == request.action_digest,
        )
    )
    valid = []
    role = request.requirements["required_role"]
    for d in decisions:
        member = tx.find(Membership, d.membership_id)
        if member and member.status == "ACTIVE" and role in member.roles:
            valid.append(d)
    return valid


def decisions_for(tx: TenantSession, request_id: uuid.UUID) -> list[ApprovalDecision]:
    return list(
        tx.scalars(
            tx.select(ApprovalDecision)
            .where(ApprovalDecision.request_id == request_id)
            .order_by(ApprovalDecision.created_at)
        )
    )


def current_request(tx: TenantSession, proposal_id: uuid.UUID) -> ApprovalRequest | None:
    return tx.first(
        tx.select(ApprovalRequest)
        .where(ApprovalRequest.proposal_id == proposal_id)
        .order_by(ApprovalRequest.created_at.desc())
    )


# -- invalidation -----------------------------------------------------------------


@proposals.on_invalidated
def _stale_requests(tx: TenantSession, proposal: ActionProposal, reason: str) -> None:
    for request in tx.scalars(
        tx.select(ApprovalRequest)
        .where(
            ApprovalRequest.proposal_id == proposal.id,
            ApprovalRequest.state.in_([RequestState.PENDING, RequestState.APPROVED]),
        )
        .with_for_update()
    ):
        _set(tx, request, RequestState.STALE, reason)
    case = tx.get(Case, proposal.case_id)
    if case.status == CaseStatus.READY_FOR_ACTION:
        cases.transition(tx, case, CaseStatus.IN_REVIEW, reason=reason)


@action_handlers.on_policy_published
def _policy_changed(tx: TenantSession) -> None:
    """A new payment policy may change approval requirements: approvals must be redone."""
    for proposal in tx.scalars(
        tx.select(ActionProposal)
        .where(ActionProposal.state.in_([ProposalState.AWAITING_APPROVAL, ProposalState.APPROVED]))
        .with_for_update()
    ):
        proposals.invalidate(tx, proposal, "Payment policy changed; re-propose for approval")


def summary(tx: TenantSession, proposal: ActionProposal) -> dict:
    request = current_request(tx, proposal.id)
    if request is None:
        return {"approval": None}
    return {
        "approval": {
            "id": request.id,
            "state": effective_state(request),
            "state_reason": request.state_reason,
            "required_count": request.required_count,
            "approved_count": len(valid_approvals(tx, request)),
            "expires_at": request.expires_at,
            "action_digest": request.action_digest,
            "revision": request.revision,
            "decisions": [
                {
                    "actor_subject": d.actor_subject,
                    "decision": d.decision,
                    "reason": d.reason,
                    "created_at": d.created_at,
                }
                for d in decisions_for(tx, request.id)
            ],
        }
    }


action_handlers.extend_view(summary)


def evaluation_of(tx: TenantSession, request: ApprovalRequest) -> Evaluation:
    return tx.get(Evaluation, request.evaluation_id)
