from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.errors import InvalidInput
from backend.evidence import service as evidence
from backend.evidence.models import DocumentVersion
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.runtime import Runtime

router = APIRouter(prefix="/v1", tags=["evidence"])


class UploadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=255)
    media_type: str
    size: int = Field(gt=0)
    declared_sha256: str
    document_id: uuid.UUID | None = None


class DocumentOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version: int
    original_name: str
    media_type: str
    size: int | None
    sha256: str | None
    status: str
    malware_status: str
    rejection_reason: str | None
    uploaded_by: str
    created_at: datetime

    @classmethod
    def of(cls, d: DocumentVersion) -> DocumentOut:
        return cls.model_validate(d, from_attributes=True)


@router.post("/uploads", status_code=201)
def create_upload(
    body: UploadCreate,
    actor: Actor = Depends(require(Capability.DOCUMENT_UPLOAD)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        doc, token, expires = evidence.create_upload(
            tx,
            actor,
            rt.settings,
            rt.grants,
            filename=body.filename,
            media_type=body.media_type,
            size=body.size,
            declared_sha256=body.declared_sha256,
            document_id=body.document_id,
        )
        return {
            "document_version_id": str(doc.id),
            "document_id": str(doc.document_id),
            "version": doc.version,
            "upload_url": f"/v1/object-grants/{token}",
            "expires_at": expires,
        }


@router.put("/object-grants/{token}", status_code=204)
async def put_object(token: str, request: Request, rt: Runtime = Depends(get_runtime)):
    declared = request.headers.get("content-length")
    if declared and int(declared) > rt.settings.max_upload_bytes:
        raise InvalidInput("Upload too large", code="FILE_SIZE")
    data = await request.body()
    evidence.receive_bytes(rt.objects, rt.grants, token, data)
    return Response(status_code=204)


@router.get("/object-grants/{token}")
def get_object(token: str, rt: Runtime = Depends(get_runtime)):
    grant = rt.grants.verify(token, "download")
    with rt.db.tenant(grant.organization_id) as tx:
        doc = evidence.require_clean(tx, grant.document_version_id)
    data = rt.objects.get(grant.organization_id, grant.object_key)
    return Response(
        content=data,
        media_type=doc.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{doc.original_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/uploads/{version_id}/complete", status_code=202, response_model=DocumentOut)
def complete_upload(
    version_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.DOCUMENT_UPLOAD)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return DocumentOut.of(
            evidence.complete_upload(tx, actor, rt.objects, rt.scanner, version_id)
        )


@router.get("/documents/{version_id}", response_model=DocumentOut)
def get_document(
    version_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return DocumentOut.of(tx.get(DocumentVersion, version_id))


@router.post("/documents/{version_id}/download-grants", status_code=201)
def download_grant(
    version_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        token, expires = evidence.download_grant(tx, actor, rt.grants, version_id)
    return {"download_url": f"/v1/object-grants/{token}", "expires_at": expires}
