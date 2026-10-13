"""Plain-language explanations of saved findings.

Generated after an evaluation commits, from its stored findings only. The
explanation is advisory text: a failure leaves the policy outcome untouched.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.adapters.models.base import FindingSummaryInput, ModelUnavailable
from backend.ai import gateway
from backend.persistence.base import Base, TenantMixin, TimestampMixin
from backend.persistence.database import TenantSession
from backend.persistence.jobs import RetryableError
from backend.policies import service as policies
from backend.policies.models import Evaluation
from backend.worker import JobContext, registry


class EvaluationExplanation(TenantMixin, TimestampMixin, Base):
    __tablename__ = "evaluation_explanation"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "evaluation_id"], ["evaluation.organization_id", "evaluation.id"]
        ),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    summary: Mapped[str] = mapped_column(String(2000))
    model_version: Mapped[str] = mapped_column(String(200))


def latest_for(tx: TenantSession, evaluation_id: uuid.UUID) -> EvaluationExplanation | None:
    return tx.first(
        tx.select(EvaluationExplanation)
        .where(EvaluationExplanation.evaluation_id == evaluation_id)
        .order_by(EvaluationExplanation.created_at.desc())
    )


@registry.consumer("evaluation.completed", "explain-evaluation")
def explain_evaluation(ctx: JobContext) -> None:
    evaluation_id = uuid.UUID(ctx.job.payload["evaluation_id"])
    with ctx.runtime.db.tenant(ctx.job.organization_id) as tx:
        evaluation = tx.get(Evaluation, evaluation_id)
        if latest_for(tx, evaluation_id) is not None:
            return  # duplicate delivery
        outcome = evaluation.outcome
        findings = [
            FindingSummaryInput(
                rule_code=v.finding.rule_code,
                effect=v.finding.effect,
                reason_code=v.finding.reason_code,
                message=v.finding.message,
            )
            for v in policies.findings_for(tx, evaluation_id)
        ]
    provider = ctx.runtime.models
    try:
        summary, _ = gateway.explain(provider, outcome, findings)
    except ModelUnavailable as exc:
        raise RetryableError(str(exc), code="MODEL_UNAVAILABLE") from exc
    with ctx.fenced() as tx:
        tx.add(
            EvaluationExplanation(
                evaluation_id=evaluation_id, summary=summary, model_version=provider.model_version
            )
        )
