from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func

from apps.api.deps import get_runtime, require, tenant_tx
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.modules.reconciliation import service as recon
from backend.modules.reconciliation.models import (
    ImportBatch,
    MatchAllocation,
    MatchGroup,
    ReconciliationException,
    SourceTransaction,
)
from backend.persistence.database import TenantSession
from backend.runtime import Runtime
from backend.telemetry import audit

router = APIRouter(prefix="/v1/reconciliation", tags=["reconciliation"])


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportIn(Strict):
    document_version_id: uuid.UUID
    side: str = Field(pattern="^(BANK|LEDGER)$")
    mapping: recon.Mapping


class DecisionIn(Strict):
    expected_version: int
    reason: str = Field(min_length=3, max_length=1000)


class ResolveIn(Strict):
    resolution_code: str = Field(pattern=r"^[A-Z_]{3,60}$")
    note: str = Field(min_length=3, max_length=1000)


def _batch_out(b: ImportBatch) -> dict:
    return {
        "id": str(b.id),
        "side": b.side,
        "state": b.state,
        "row_count": b.row_count,
        "imported_count": b.imported_count,
        "errors": b.errors,
        "document_version_id": str(b.document_version_id),
        "created_at": b.created_at.isoformat(),
    }


def _match_out(tx: TenantSession, g: MatchGroup) -> dict:
    allocs = tx.scalars(tx.select(MatchAllocation).where(MatchAllocation.group_id == g.id))
    return {
        "id": str(g.id),
        "state": g.state,
        "version": g.version,
        "match_type": g.match_type,
        "basis": g.basis,
        "decided_by": g.decided_by,
        "reason": g.reason,
        "rows": [
            recon.row_view(tx.get(SourceTransaction, a.source_transaction_id)) for a in allocs
        ],
    }


@router.post("/imports", status_code=202)
def request_import(
    body: ImportIn,
    actor: Actor = Depends(require(Capability.RECON_IMPORT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        batch = recon.request_import(
            tx,
            actor,
            document_version_id=body.document_version_id,
            side=body.side,
            mapping=body.mapping,
        )
        return _batch_out(batch)


@router.get("/imports")
def list_imports(
    actor: Actor = Depends(require(Capability.CASE_READ)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        rows = tx.scalars(tx.select(ImportBatch).order_by(ImportBatch.created_at.desc()))
        return [_batch_out(b) for b in rows]


@router.get("/summary")
def summary(
    actor: Actor = Depends(require(Capability.CASE_READ)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        counts = tx.session.execute(
            tx.select(SourceTransaction)
            .with_only_columns(SourceTransaction.side, SourceTransaction.status, func.count())
            .group_by(SourceTransaction.side, SourceTransaction.status)
        ).all()
        open_exceptions = tx.session.scalar(
            tx.select(ReconciliationException)
            .with_only_columns(func.count())
            .where(ReconciliationException.state == "OPEN")
        )
        return {
            "transactions": [{"side": s, "status": st, "count": c} for s, st, c in counts],
            "open_exceptions": open_exceptions,
        }


@router.get("/transactions")
def list_transactions(
    side: str | None = None,
    status: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        stmt = tx.select(SourceTransaction).order_by(
            SourceTransaction.booked_on, SourceTransaction.external_id
        )
        if side:
            stmt = stmt.where(SourceTransaction.side == side)
        if status:
            stmt = stmt.where(SourceTransaction.status == status)
        return [recon.row_view(r) for r in tx.scalars(stmt.limit(limit))]


@router.get("/matches")
def list_matches(
    state: str | None = "PROPOSED",
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        stmt = tx.select(MatchGroup).order_by(MatchGroup.created_at)
        if state:
            stmt = stmt.where(MatchGroup.state == state)
        return [_match_out(tx, g) for g in tx.scalars(stmt)]


@router.post("/matches/{group_id}/approve")
def approve_match(
    group_id: uuid.UUID,
    body: DecisionIn,
    actor: Actor = Depends(require(Capability.RECON_MATCH_APPROVE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        group = recon.decide_match(
            tx,
            actor,
            group_id,
            approve=True,
            expected_version=body.expected_version,
            reason=body.reason,
        )
        return _match_out(tx, group)


@router.post("/matches/{group_id}/reject")
def reject_match(
    group_id: uuid.UUID,
    body: DecisionIn,
    actor: Actor = Depends(require(Capability.RECON_MATCH_APPROVE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        group = recon.decide_match(
            tx,
            actor,
            group_id,
            approve=False,
            expected_version=body.expected_version,
            reason=body.reason,
        )
        return _match_out(tx, group)


@router.get("/exceptions")
def list_exceptions(
    state: str | None = "OPEN",
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        stmt = tx.select(ReconciliationException).order_by(ReconciliationException.created_at)
        if state:
            stmt = stmt.where(ReconciliationException.state == state)
        return [
            {
                "id": str(e.id),
                "case_id": str(e.case_id),
                "kind": e.kind,
                "state": e.state,
                "details": e.details,
                "transaction": recon.row_view(tx.get(SourceTransaction, e.source_transaction_id)),
            }
            for e in tx.scalars(stmt)
        ]


@router.post("/exceptions/{exception_id}/resolve")
def resolve_exception(
    exception_id: uuid.UUID,
    body: ResolveIn,
    actor: Actor = Depends(require(Capability.RECON_MATCH_APPROVE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        exc = recon.resolve_exception(
            tx, actor, exception_id, resolution_code=body.resolution_code, note=body.note
        )
        return {"id": str(exc.id), "state": exc.state, "resolution_code": exc.resolution_code}


@router.get("/export")
def export(
    actor: Actor = Depends(require(Capability.AUDIT_EXPORT)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        content = recon.export_rows(tx)
        audit.record(
            tx, "reconciliation.exported", object_type="organization", object_id=tx.organization_id
        )
    return Response(
        content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="reconciliation-export.csv"'},
    )
