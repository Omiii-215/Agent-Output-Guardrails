"""Worker jobs for reservation, submission, reconciliation and provider events."""

from __future__ import annotations

import uuid

from backend.adapters.payments.simulator import ProviderTimeout
from backend.persistence.jobs import RetryableError
from backend.worker import JobContext, registry

from . import execution
from .models import ActionIntent, IntentState, WebhookReceipt


@registry.handler(execution.RESERVE_JOB)
def reserve(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        execution.reserve(tx, ctx.job.object_ref, created_by=ctx.actor.subject)


@registry.handler(execution.EXECUTE_JOB)
def execute(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        claimed = execution.claim(tx, ctx.job.object_ref)
    if claimed is None:
        return
    intent, action = claimed
    # Network call outside any database transaction.
    result, timed_out = execution.submit(ctx.runtime.payments, intent, action)
    with ctx.fenced() as tx:
        execution.record_submission(tx, intent.id, result, timed_out=timed_out)


@registry.handler(execution.RECONCILE_JOB)
def reconcile(ctx: JobContext) -> None:
    with ctx.runtime.db.tenant(ctx.job.organization_id) as tx:
        intent = tx.get(ActionIntent, ctx.job.object_ref)
        if intent.state != IntentState.UNKNOWN:
            return
        key = intent.provider_idempotency_key
    try:
        status = ctx.runtime.payments.status(ctx.job.organization_id, key)
    except ProviderTimeout as exc:
        raise RetryableError(str(exc), code="PROVIDER_STATUS_TIMEOUT") from exc
    with ctx.fenced() as tx:
        execution.apply_status(tx, ctx.job.object_ref, status)


@registry.handler(execution.WEBHOOK_JOB)
def process_webhook(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        receipt = tx.get(WebhookReceipt, uuid.UUID(ctx.job.payload["receipt_id"]), for_update=True)
        if receipt.processing_state == "PROCESSED":
            return
        receipt.processing_state = "PROCESSED:" + execution.apply_event(tx, receipt.payload)
