from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from apps.api.routes.cases import AuditOut
from backend.audit import exports
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.runtime import Runtime
from backend.telemetry.audit import AuditEvent

router = APIRouter(prefix="/v1", tags=["audit"])


class ExportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    purpose: str = Field(min_length=5, max_length=500)
    case_ids: list[uuid.UUID] | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None


def _out(e: exports.AuditExport) -> dict:
    return {
        "id": str(e.id),
        "state": e.state,
        "purpose": e.purpose,
        "case_count": e.case_count,
        "bundle_digest": e.bundle_digest,
        "requested_by": e.requested_by,
        "expires_at": e.expires_at.isoformat() if e.expires_at else None,
    }


@router.post("/audit-exports", status_code=202)
def request_export(
    body: ExportIn,
    actor: Actor = Depends(require(Capability.AUDIT_EXPORT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _out(
            exports.request_export(
                tx,
                actor,
                purpose=body.purpose,
                case_ids=body.case_ids,
                from_date=body.from_date,
                to_date=body.to_date,
            )
        )


@router.get("/audit-exports/{export_id}")
def get_export(
    export_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.AUDIT_EXPORT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return _out(tx.get(exports.AuditExport, export_id))


@router.get("/audit-exports/{export_id}/download")
def download_export(
    export_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.AUDIT_EXPORT)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        export = exports.download(tx, actor, export_id)
        key = export.object_key
    return Response(
        rt.objects.get(actor.organization_id, key),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="audit-export-{export_id}.json"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/audit/events", response_model=list[AuditOut])
def audit_events(
    action: str | None = None,
    object_id: uuid.UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    actor: Actor = Depends(require(Capability.AUDIT_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        stmt = tx.select(AuditEvent).order_by(AuditEvent.occurred_at.desc())
        if action:
            stmt = stmt.where(AuditEvent.action == action)
        if object_id:
            stmt = stmt.where(AuditEvent.object_id == object_id)
        return [AuditOut.of(e) for e in tx.scalars(stmt.limit(limit))]
