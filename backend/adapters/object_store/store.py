"""Object storage adapters.

Keys are always prefixed with the owning organization ID; every read and write
states the organization and the adapter refuses keys outside that prefix. The
local filesystem adapter is for synthetic development data. The pilot S3
adapter implements the same protocol with private buckets and presigned URLs.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Protocol

from backend.errors import NotFound


class ObjectStore(Protocol):
    def put(self, organization_id: uuid.UUID, key: str, data: bytes) -> None: ...
    def get(self, organization_id: uuid.UUID, key: str) -> bytes: ...
    def exists(self, organization_id: uuid.UUID, key: str) -> bool: ...


def object_key(organization_id: uuid.UUID, *parts: str) -> str:
    return "/".join((str(organization_id), *parts))


def _check_prefix(organization_id: uuid.UUID, key: str) -> None:
    if not key.startswith(f"{organization_id}/") or ".." in key.split("/"):
        raise NotFound("Object not found")


class LocalObjectStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _path(self, organization_id: uuid.UUID, key: str) -> Path:
        _check_prefix(organization_id, key)
        return self.root / key

    def put(self, organization_id: uuid.UUID, key: str, data: bytes) -> None:
        path = self._path(organization_id, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".partial")
        tmp.write_bytes(data)
        tmp.replace(path)

    def get(self, organization_id: uuid.UUID, key: str) -> bytes:
        path = self._path(organization_id, key)
        if not path.is_file():
            raise NotFound("Object not found")
        return path.read_bytes()

    def exists(self, organization_id: uuid.UUID, key: str) -> bool:
        return self._path(organization_id, key).is_file()
