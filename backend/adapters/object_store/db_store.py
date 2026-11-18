"""Object storage in PostgreSQL, for hosts without a persistent shared disk.

Serverless functions (and free container hosts that sleep) lose their local
filesystem between requests, so uploaded documents and evidence exports are
kept in a tenant-owned table instead. Rows carry the owning organization and
are protected by the same row-level security as every other tenant table; the
key prefix check from the filesystem adapter still applies.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, LargeBinary, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.adapters.object_store.store import _check_prefix
from backend.errors import NotFound
from backend.persistence.base import Base, TenantMixin, TimestampMixin
from backend.persistence.database import Database


class StoredObject(TenantMixin, TimestampMixin, Base):
    __tablename__ = "stored_object"
    __table_args__ = (UniqueConstraint("organization_id", "object_key"),)

    object_key: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column(Integer)
    data: Mapped[bytes] = mapped_column(LargeBinary)


class DatabaseObjectStore:
    def __init__(self, db: Database):
        self.db = db

    def _row(self, tx, key: str) -> StoredObject | None:
        return tx.first(tx.select(StoredObject).where(StoredObject.object_key == key))

    def put(self, organization_id: uuid.UUID, key: str, data: bytes) -> None:
        _check_prefix(organization_id, key)
        with self.db.tenant(organization_id) as tx:
            row = self._row(tx, key)
            if row is None:
                tx.add(StoredObject(object_key=key, size=len(data), data=data))
            else:
                row.data = data
                row.size = len(data)

    def get(self, organization_id: uuid.UUID, key: str) -> bytes:
        _check_prefix(organization_id, key)
        with self.db.tenant(organization_id) as tx:
            row = self._row(tx, key)
            if row is None:
                raise NotFound("Object not found")
            return bytes(row.data)

    def exists(self, organization_id: uuid.UUID, key: str) -> bool:
        _check_prefix(organization_id, key)
        with self.db.tenant(organization_id) as tx:
            return self._row(tx, key) is not None
