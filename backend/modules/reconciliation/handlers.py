"""Reconciliation jobs and the exception section of case detail."""

from __future__ import annotations

import uuid

from backend.cases import detail
from backend.cases.models import Case
from backend.persistence.database import TenantSession
from backend.worker import JobContext, registry

from . import service
from .models import ReconciliationException, SourceTransaction


@registry.handler(service.IMPORT_JOB)
def import_batch(ctx: JobContext) -> None:
    rt = ctx.runtime
    with rt.db.tenant(ctx.job.organization_id) as tx:
        doc = service.batch_document(tx, ctx.job.object_ref)
        key = doc.object_key
    data = rt.objects.get(ctx.job.organization_id, key)
    with ctx.fenced() as tx:
        service.run_import(tx, ctx.job.object_ref, data)


@registry.handler(service.MATCH_JOB)
def match(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        service.run_matching(tx, ctx.actor.subject)


def exception_section(tx: TenantSession, case: Case) -> detail.DetailSection:
    exc = tx.first(
        tx.select(ReconciliationException).where(ReconciliationException.case_id == case.id)
    )
    if exc is None:
        return detail.DetailSection()
    row = tx.get(SourceTransaction, exc.source_transaction_id)
    counterparts = [
        service.row_view(tx.get(SourceTransaction, uuid.UUID(i)))
        for i in exc.details.get("counterparts", [])
    ]
    return detail.DetailSection(
        data={
            "exception": {
                "id": exc.id,
                "kind": exc.kind,
                "details": exc.details,
                "state": exc.state,
                "resolution_code": exc.resolution_code,
                "resolution_note": exc.resolution_note,
                "resolved_by": exc.resolved_by,
            },
            "transaction": service.row_view(row),
            "counterparts": counterparts,
            "next_actions": ["RESOLVE_EXCEPTION"] if exc.state == "OPEN" else [],
        },
        related_ids=[exc.id, row.id],
    )


detail.register("reconciliation", exception_section)
