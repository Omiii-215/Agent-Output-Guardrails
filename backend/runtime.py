"""Process-wide wiring of adapters shared by the API and the worker."""

from __future__ import annotations

from dataclasses import dataclass

from backend.adapters.object_store.grants import GrantSigner
from backend.adapters.object_store.store import LocalObjectStore, ObjectStore
from backend.config import Settings
from backend.evidence.inspection import Scanner, SignatureScanner
from backend.persistence.database import Database


@dataclass
class Runtime:
    settings: Settings
    db: Database
    objects: ObjectStore
    grants: GrantSigner
    scanner: Scanner


def build_runtime(settings: Settings, db: Database | None = None) -> Runtime:
    return Runtime(
        settings=settings,
        db=db or Database(settings.database_url, admin_url=settings.database_admin_url),
        objects=LocalObjectStore(settings.object_store_path),
        grants=GrantSigner(settings.object_grant_secret, settings.object_grant_ttl_seconds),
        scanner=SignatureScanner(),
    )
