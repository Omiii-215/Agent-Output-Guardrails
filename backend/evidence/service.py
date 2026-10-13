"""Upload lifecycle and evidence references.

create → (client uploads bytes with a short-lived grant) → complete. ``complete``
re-reads the stored object and verifies its real size, SHA-256, sniffed media
type and scan result before the version becomes CLEAN. Anything else is
REJECTED with a reason; rejected bytes are never parsed.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func

from backend.adapters.object_store.grants import GrantSigner
from backend.adapters.object_store.store import ObjectStore, object_key
from backend.config import Settings
from backend.domain.canonical import digest, sha256_bytes
from backend.domain.clock import utcnow
from backend.errors import Conflict, InvalidInput
from backend.evidence.inspection import Scanner, media_type_matches, sniff_media_type
from backend.evidence.models import DocumentStatus, DocumentVersion, EvidenceItem
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence.database import TenantSession
from backend.telemetry import audit

_SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_NAME_RE = re.compile(r"[^A-Za-z0-9._ -]")


def _safe_name(name: str) -> str:
    cleaned = _NAME_RE.sub("_", name.replace("\\", "/").split("/")[-1]).strip()
    return cleaned[:255] or "upload"


def create_upload(
    tx: TenantSession,
    actor: Actor,
    settings: Settings,
    signer: GrantSigner,
    *,
    filename: str,
    media_type: str,
    size: int,
    declared_sha256: str,
    document_id: uuid.UUID | None = None,
) -> tuple[DocumentVersion, str, int]:
    actor.require(Capability.DOCUMENT_UPLOAD)
    if media_type not in settings.allowed_media_types:
        raise InvalidInput(f"Media type '{media_type}' is not accepted", code="MEDIA_TYPE")
    if size <= 0 or size > settings.max_upload_bytes:
        raise InvalidInput("File size is outside the permitted range", code="FILE_SIZE")
    if not _SHA256_RE.match(declared_sha256):
        raise InvalidInput("declared_sha256 must be 'sha256:<64 hex>'", code="HASH_FORMAT")

    if document_id is None:
        document_id = uuid.uuid4()
        version = 1
    else:
        latest = tx.session.scalar(
            tx.select(DocumentVersion)
            .with_only_columns(func.max(DocumentVersion.version))
            .where(DocumentVersion.document_id == document_id)
        )
        if latest is None:
            raise InvalidInput("Unknown document", code="NOT_FOUND")
        version = latest + 1

    version_id = uuid.uuid4()
    doc = tx.add(
        DocumentVersion(
            id=version_id,
            document_id=document_id,
            version=version,
            object_key=object_key(tx.organization_id, "documents", str(version_id), "original"),
            original_name=_safe_name(filename),
            media_type=media_type,
            declared_size=size,
            declared_sha256=declared_sha256,
            uploaded_by=actor.subject,
        )
    )
    tx.flush()
    token, expires = signer.issue(
        tx.organization_id, doc.object_key, doc.id, "upload", max_bytes=size
    )
    audit.record(
        tx,
        "document.upload_started",
        object_type="document_version",
        object_id=doc.id,
        data={"document_id": document_id, "version": version, "media_type": media_type},
    )
    return doc, token, expires


def receive_bytes(store: ObjectStore, signer: GrantSigner, token: str, data: bytes) -> None:
    """Store uploaded bytes in quarantine. Verification happens in ``complete``."""
    grant = signer.verify(token, "upload")
    if grant.max_bytes is not None and len(data) > grant.max_bytes:
        raise InvalidInput("Upload exceeds the declared size", code="FILE_SIZE")
    store.put(grant.organization_id, grant.object_key, data)


def complete_upload(
    tx: TenantSession,
    actor: Actor,
    store: ObjectStore,
    scanner: Scanner,
    version_id: uuid.UUID,
) -> DocumentVersion:
    actor.require(Capability.DOCUMENT_UPLOAD)
    doc = tx.get(DocumentVersion, version_id, for_update=True)
    if doc.status not in (DocumentStatus.PENDING_UPLOAD, DocumentStatus.QUARANTINED):
        return doc  # idempotent: verification already decided
    if not store.exists(tx.organization_id, doc.object_key):
        raise Conflict("No uploaded content found for this document", code="UPLOAD_MISSING")

    data = store.get(tx.organization_id, doc.object_key)
    doc.size = len(data)
    doc.sha256 = sha256_bytes(data)
    doc.status = DocumentStatus.QUARANTINED

    reason = None
    threat = scanner.scan(data)
    doc.malware_status = "INFECTED" if threat else "CLEAN"
    if threat:
        reason = f"MALWARE_DETECTED:{threat}"
    elif doc.size != doc.declared_size:
        reason = "SIZE_MISMATCH"
    elif doc.sha256 != doc.declared_sha256:
        reason = "HASH_MISMATCH"
    elif not media_type_matches(doc.media_type, sniff_media_type(data)):
        reason = "MEDIA_TYPE_MISMATCH"

    doc.status = DocumentStatus.REJECTED if reason else DocumentStatus.CLEAN
    doc.rejection_reason = reason
    doc.verified_at = utcnow()
    audit.record(
        tx,
        "document.rejected" if reason else "document.verified",
        object_type="document_version",
        object_id=doc.id,
        reason=reason,
        data={"sha256": doc.sha256, "size": doc.size},
    )
    return doc


def download_grant(
    tx: TenantSession, actor: Actor, signer: GrantSigner, version_id: uuid.UUID
) -> tuple[str, int]:
    actor.require(Capability.CASE_READ)
    doc = tx.get(DocumentVersion, version_id)
    if doc.status != DocumentStatus.CLEAN:
        raise Conflict("Only verified documents can be downloaded", code="DOCUMENT_NOT_CLEAN")
    audit.record(tx, "document.download_granted", object_type="document_version", object_id=doc.id)
    return signer.issue(tx.organization_id, doc.object_key, doc.id, "download")


def require_clean(tx: TenantSession, version_id: uuid.UUID) -> DocumentVersion:
    doc = tx.get(DocumentVersion, version_id)
    if doc.status != DocumentStatus.CLEAN:
        raise Conflict("Document has not passed verification", code="DOCUMENT_NOT_CLEAN")
    return doc


def record_evidence(
    tx: TenantSession,
    *,
    source_type: str,
    source_ref: str,
    locator: dict[str, Any],
    excerpt: str | None = None,
    document_version_id: uuid.UUID | None = None,
    valid_until: datetime | None = None,
) -> EvidenceItem:
    """Append an evidence reference. Its integrity hash covers source and locator."""
    if document_version_id is not None:
        tx.get(DocumentVersion, document_version_id)  # same-tenant check
    item = tx.add(
        EvidenceItem(
            source_type=source_type,
            source_ref=source_ref,
            document_version_id=document_version_id,
            locator=locator,
            excerpt=excerpt[:2000] if excerpt else None,
            integrity_hash=digest(
                {
                    "source_type": source_type,
                    "source_ref": source_ref,
                    "document_version_id": document_version_id,
                    "locator": locator,
                    "excerpt": excerpt,
                }
            ),
            valid_until=valid_until,
            recorded_by=str(getattr(tx.actor, "subject", "system")),
        )
    )
    tx.flush()
    return item
