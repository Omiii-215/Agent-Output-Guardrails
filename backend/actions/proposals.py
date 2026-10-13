"""Action proposals and preflight (LLD §6–8, diagram 06).

The client submits requested fields only. The server resolves tenant-owned
records, validates money and payee, serialises a canonical payload with a
versioned algorithm and computes the digest itself. A digest supplied by a
client is an unknown field. Changing amount, payee, purpose or mode requires a
new proposal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.actions import sources
from backend.actions.models import (
    ACTIVE_PROPOSAL_STATES,
    ActionControl,
    ActionProposal,
    ProposalState,
)
from backend.actions.spend import bucket_view
from backend.cases import hooks
from backend.cases import service as cases
from backend.cases.models import Case, CaseStatus
from backend.domain.canonical import CANON_ALGORITHM, digest
from backend.domain.clock import utcnow
from backend.domain.money import Money, MoneyError
from backend.errors import Conflict, InvalidInput
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence import jobs
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.telemetry import audit

PAYLOAD_SCHEMA = "payment-proposal-v1"
POLICY_CODE = "payment-preflight"
PREFLIGHT_JOB = "actions.preflight"
FIRST_RELEASE_MODES = frozenset({"SIMULATED"})


@dataclass(frozen=True)
class ProposalRequest:
    case_id: uuid.UUID
    expected_case_revision: int
    action_type: str
    amount_minor: str
    currency: str
    beneficiary_version_id: uuid.UUID
    purpose: str
    mode: str
    source_references: tuple[str, ...] = ()


def _evaluation_eligible(ev: dict | None) -> bool:
    if not ev or not ev.get("current"):
        return False
    return ev["outcome"] == "PASS" or (ev["outcome"] == "REVIEW" and ev["unresolved"] == 0)


def set_state(
    tx: TenantSession, proposal: ActionProposal, state: str, reason: str | None = None
) -> None:
    previous = proposal.state
    proposal.state = state
    proposal.state_reason = reason
    proposal.revision += 1
    proposal.updated_at = utcnow()
    audit.record(
        tx,
        "proposal.state_changed",
        object_type="action_proposal",
        object_id=proposal.id,
        reason=reason,
        data={"from": previous, "to": state, "case_id": proposal.case_id},
        simulated=proposal.mode == "SIMULATED",
    )


def create_proposal(tx: TenantSession, actor: Actor, req: ProposalRequest) -> ActionProposal:
    actor.require(Capability.PROPOSAL_CREATE)
    if req.action_type != "PAYMENT":
        raise InvalidInput("Only PAYMENT actions are supported", code="ACTION_TYPE")
    if req.mode not in FIRST_RELEASE_MODES:
        raise InvalidInput(
            "Only SIMULATED payments are enabled in this release", code="MODE_NOT_ALLOWED"
        )
    case = cases.get_for_update(tx, req.case_id)
    cases.check_revision(case, req.expected_case_revision)
    if case.status != CaseStatus.IN_REVIEW:
        raise Conflict(f"Case is {case.status}; it must be IN_REVIEW", code="CASE_NOT_IN_REVIEW")
    try:
        amount = Money.of(req.amount_minor, req.currency)
    except MoneyError as exc:
        raise InvalidInput(str(exc), code="INVALID_AMOUNT") from None

    facts = sources.facts_for(tx, case)
    if amount != facts.expected_amount:
        raise InvalidInput(
            "Amount must equal the reviewed payable amount",
            code="AMOUNT_MISMATCH",
            details={"expected": facts.expected_amount.to_api()},
        )
    if not facts.beneficiary or str(req.beneficiary_version_id) != str(
        facts.beneficiary["beneficiary_version_id"]
    ):
        raise Conflict(
            "Payee is not the vendor's current bank account", code="BENEFICIARY_NOT_CURRENT"
        )
    if not _evaluation_eligible(facts.document_evaluation):
        raise Conflict(
            "The case has no current, eligible evaluation", code="EVALUATION_NOT_ELIGIBLE"
        )
    active = tx.first(
        tx.select(ActionProposal).where(
            ActionProposal.case_id == case.id,
            ActionProposal.state.in_(ACTIVE_PROPOSAL_STATES),
        )
    )
    if active is not None:
        raise Conflict(
            "An active proposal already exists for this case",
            code="PROPOSAL_EXISTS",
            details={"proposal_id": str(active.id)},
        )

    proposal_id = uuid.uuid4()
    payload = policies.freeze_inputs(
        {
            "schema": PAYLOAD_SCHEMA,
            "proposal_id": proposal_id,
            "organization_id": tx.organization_id,
            "case_id": case.id,
            "action_type": req.action_type,
            "mode": req.mode,
            "amount_minor": amount.minor,
            "currency": amount.currency,
            "beneficiary": facts.beneficiary,
            "vendor_id": facts.vendor_id,
            "subject": facts.subject,
            "purpose": req.purpose,
            "document_evaluation_id": facts.document_evaluation["evaluation_id"],
            "source_references": list(req.source_references),
        }
    )
    proposal = tx.add(
        ActionProposal(
            id=proposal_id,
            case_id=case.id,
            maker_subject=actor.subject,
            maker_actor_type=actor.actor_type,
            action_type=req.action_type,
            mode=req.mode,
            canonical_payload=payload,
            payload_algorithm=CANON_ALGORITHM,
            digest=digest(payload),
            amount_minor=amount.minor,
            currency=amount.currency,
            source_revision_map=policies.freeze_inputs(facts.source_revisions),
        )
    )
    tx.flush()
    audit.record(
        tx,
        "proposal.created",
        object_type="action_proposal",
        object_id=proposal.id,
        data={
            "case_id": case.id,
            "digest": proposal.digest,
            "amount": amount.to_api(),
            "mode": req.mode,
            "maker_actor_type": actor.actor_type,
        },
        simulated=req.mode == "SIMULATED",
    )
    audit.record(
        tx,
        "case.proposal_created",
        object_type="case",
        object_id=case.id,
        data={"proposal_id": proposal.id, "digest": proposal.digest},
    )
    jobs.enqueue(
        tx, PREFLIGHT_JOB, object_ref=proposal.id, dedupe_key=f"{proposal.id}:{proposal.revision}"
    )
    return proposal


# -- preflight ----------------------------------------------------------------


def control_for(tx: TenantSession) -> ActionControl | None:
    return tx.first(tx.select(ActionControl))


def build_preflight_inputs(tx: TenantSession, proposal: ActionProposal) -> tuple[dict, dict]:
    case = tx.get(Case, proposal.case_id)
    facts = sources.facts_for(tx, case)
    changed = [
        key
        for key, value in proposal.source_revision_map.items()
        if str(facts.source_revisions.get(key)) != str(value)
    ]
    control = control_for(tx)
    others = tx.scalars(
        tx.select(ActionProposal).where(
            ActionProposal.case_id == case.id,
            ActionProposal.id != proposal.id,
            ActionProposal.state.in_(ACTIVE_PROPOSAL_STATES),
        )
    )
    doc = policies.document_of(policies.active_policy(tx, POLICY_CODE))
    ben = facts.beneficiary or {}
    frozen_ben = proposal.canonical_payload.get("beneficiary") or {}
    inputs = {
        "proposal": {
            "proposal_id": proposal.id,
            "digest": proposal.digest,
            "recomputed_digest": digest(proposal.canonical_payload),
            "mode": proposal.mode,
            "amount_minor": proposal.amount_minor,
            "currency": proposal.currency,
        },
        "controls": {
            "halted": bool(control and control.halted),
            "reason": control.reason if control else None,
        },
        "source": {"stale": bool(changed), "changed": changed},
        "document_evaluation": facts.document_evaluation,
        "beneficiary": {
            "matches_current": str(ben.get("beneficiary_version_id"))
            == str(frozen_ben.get("beneficiary_version_id"))
            and ben.get("account_fingerprint") == frozen_ben.get("account_fingerprint"),
            "verification_status": ben.get("verification_status"),
        },
        "duplicates": {
            "other_active_proposals": [str(o.id) for o in others],
            "executed": facts.executed_references,
        },
        "spend": bucket_view(tx, doc, proposal.currency),
    }
    return inputs, {**facts.source_revisions, "proposal_revision": proposal.revision}


def run_preflight(tx: TenantSession, proposal_id: uuid.UUID, created_by: str) -> None:
    proposal = tx.get(ActionProposal, proposal_id, for_update=True)
    if proposal.state != ProposalState.PREFLIGHT_PENDING:
        return
    case = tx.get(Case, proposal.case_id)
    inputs, revisions = build_preflight_inputs(tx, proposal)
    evaluation = policies.record_evaluation(
        tx,
        case=case,
        kind="ACTION",
        inputs=inputs,
        source_revision_map=revisions,
        policy=policies.active_policy(tx, POLICY_CODE),
        created_by=created_by,
        proposal_id=proposal.id,
    )
    next_state = {
        "PASS": ProposalState.READY_FOR_APPROVAL,
        "REVIEW": ProposalState.NEEDS_REVIEW,
    }.get(evaluation.outcome, ProposalState.BLOCKED)
    set_state(tx, proposal, next_state, reason=f"Preflight {evaluation.outcome}")


def latest_action_evaluation(tx: TenantSession, proposal: ActionProposal):
    from backend.policies.models import Evaluation

    return tx.first(
        tx.select(Evaluation)
        .where(Evaluation.proposal_id == proposal.id, Evaluation.kind == "ACTION")
        .order_by(Evaluation.created_at.desc(), Evaluation.id.desc())
    )


def requeue_preflight(tx: TenantSession, proposal: ActionProposal, reason: str) -> None:
    set_state(tx, proposal, ProposalState.PREFLIGHT_PENDING, reason)
    jobs.enqueue(
        tx, PREFLIGHT_JOB, object_ref=proposal.id, dedupe_key=f"{proposal.id}:{proposal.revision}"
    )


# -- invalidation and controls -----------------------------------------------------

# States that a material input change turns STALE. INTENT_CREATED is handled by
# the execution gateway, which checks whether a submission was already claimed.
_INVALIDATE_ON_CHANGE = frozenset(
    {
        ProposalState.PREFLIGHT_PENDING,
        ProposalState.READY_FOR_APPROVAL,
        ProposalState.NEEDS_REVIEW,
        ProposalState.AWAITING_APPROVAL,
        ProposalState.APPROVED,
    }
)

_invalidation_listeners: list = []


def on_invalidated(listener):
    """Register a callback(tx, proposal, reason) run when a proposal turns STALE."""
    _invalidation_listeners.append(listener)
    return listener


def invalidate(tx: TenantSession, proposal: ActionProposal, reason: str) -> None:
    set_state(tx, proposal, ProposalState.STALE, reason)
    for listener in _invalidation_listeners:
        listener(tx, proposal, reason)


@hooks.on_inputs_changed
def _invalidate_for_case(tx: TenantSession, case: Case, reason: str) -> None:
    for proposal in tx.scalars(
        tx.select(ActionProposal)
        .where(
            ActionProposal.case_id == case.id,
            ActionProposal.state.in_(_INVALIDATE_ON_CHANGE),
        )
        .with_for_update()
    ):
        invalidate(tx, proposal, f"Material input changed: {reason}")


def set_halt(tx: TenantSession, actor: Actor, *, halted: bool, reason: str) -> ActionControl:
    actor.require(Capability.ACTION_HALT)
    control = tx.first(tx.select(ActionControl).with_for_update())
    if control is None:
        control = tx.add(ActionControl())
    control.halted = halted
    control.reason = reason
    control.changed_by = actor.subject
    control.changed_at = utcnow()
    tx.flush()
    audit.record(
        tx,
        "actions.halted" if halted else "actions.resumed",
        object_type="action_control",
        object_id=control.id,
        reason=reason,
    )
    return control
