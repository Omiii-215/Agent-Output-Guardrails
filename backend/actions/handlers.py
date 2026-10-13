"""Gateway jobs, event consumers and the case-detail section for actions."""

from __future__ import annotations

from typing import Any

from backend.cases import detail
from backend.cases.models import Case
from backend.domain.money import Money
from backend.persistence.database import TenantSession
from backend.policies import service as policies
from backend.worker import JobContext, registry

from . import proposals
from .models import ActionProposal, ProposalState


@registry.handler(proposals.PREFLIGHT_JOB)
def preflight(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        proposals.run_preflight(tx, ctx.job.object_ref, created_by=ctx.actor.subject)


# Proposals not yet approved are simply re-checked under the new policy.
_RECHECK_ON_POLICY = (ProposalState.READY_FOR_APPROVAL, ProposalState.NEEDS_REVIEW)


@registry.consumer("policy.published", "actions-policy-rollout")
def policy_rollout(ctx: JobContext) -> None:
    if ctx.job.payload.get("policy_code") != proposals.POLICY_CODE:
        return
    with ctx.fenced() as tx:
        for proposal in tx.scalars(
            tx.select(ActionProposal)
            .where(ActionProposal.state.in_(_RECHECK_ON_POLICY))
            .with_for_update()
        ):
            proposals.requeue_preflight(tx, proposal, "New payment policy published")
        for listener in _policy_listeners:
            listener(tx)


_policy_listeners: list = []


def on_policy_published(listener):
    _policy_listeners.append(listener)
    return listener


def proposal_view(tx: TenantSession, p: ActionProposal) -> dict[str, Any]:
    evaluation = proposals.latest_action_evaluation(tx, p)
    findings = []
    if evaluation is not None:
        findings = [
            {
                "rule_code": v.finding.rule_code,
                "result": v.finding.result,
                "effect": v.finding.effect,
                "reason_code": v.finding.reason_code,
                "message": v.finding.message,
            }
            for v in policies.findings_for(tx, evaluation.id)
        ]
    money = Money(p.amount_minor, p.currency)
    view = {
        "id": p.id,
        "state": p.state,
        "state_reason": p.state_reason,
        "mode": p.mode,
        "simulated": p.mode == "SIMULATED",
        "action_type": p.action_type,
        "amount": {**money.to_api(), "formatted": money.format()},
        "digest": p.digest,
        "payload_algorithm": p.payload_algorithm,
        "payload": p.canonical_payload,
        "maker_subject": p.maker_subject,
        "maker_actor_type": p.maker_actor_type,
        "revision": p.revision,
        "created_at": p.created_at,
        "preflight": (
            {"evaluation_id": evaluation.id, "outcome": evaluation.outcome, "findings": findings}
            if evaluation
            else None
        ),
    }
    for extend in _view_extensions:
        view.update(extend(tx, p))
    return view


_view_extensions: list = []


def extend_view(fn):
    _view_extensions.append(fn)
    return fn


def proposals_section(tx: TenantSession, case: Case) -> detail.DetailSection:
    rows = tx.scalars(
        tx.select(ActionProposal)
        .where(ActionProposal.case_id == case.id)
        .order_by(ActionProposal.created_at.desc())
    )
    return detail.DetailSection(
        data={"proposals": [proposal_view(tx, p) for p in rows]},
        related_ids=[p.id for p in rows],
    )


detail.register("invoices", proposals_section)
