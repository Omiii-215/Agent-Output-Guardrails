"""Audit export job."""

from __future__ import annotations

from backend.domain.clock import utcnow
from backend.telemetry import audit
from backend.worker import JobContext, registry

from . import exports


@registry.handler(exports.EXPORT_JOB)
def build_export(ctx: JobContext) -> None:
    with ctx.fenced() as tx:
        result = exports.build(tx, ctx.job.object_ref)
        if result is None:
            return
        export, content = result
        ctx.runtime.objects.put(ctx.job.organization_id, export.object_key, content)
        export.state = "READY"
        export.expires_at = utcnow() + exports.EXPORT_TTL
        audit.record(
            tx,
            "audit_export.ready",
            object_type="audit_export",
            object_id=export.id,
            data={"cases": export.case_count, "bundle_digest": export.bundle_digest},
        )
