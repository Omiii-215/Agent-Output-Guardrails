"""Declarative base, portable column types and tenant mixins.

Every tenant-owned table uses a composite primary key ``(organization_id, id)``
so children can reference parents through composite foreign keys and never
point at another tenant's row (ADR 0003).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, MetaData, TypeDecorator, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from backend.domain.clock import ensure_aware, new_id, utcnow

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-aware timestamps on every dialect (SQLite returns naive values)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Naive datetimes are not stored; use timezone-aware UTC")
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        return ensure_aware(value) if value is not None else None


JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {
        datetime: UTCDateTime(),
        uuid.UUID: Uuid(),
        dict[str, Any]: JSONType,
        list[Any]: JSONType,
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class TenantMixin:
    """Tenant-owned row: composite key ``(organization_id, id)``.

    The ``__tenant_owned__`` marker drives repository scoping and the RLS
    migration helper.
    """

    __tenant_owned__ = True

    @declared_attr
    def organization_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("organization.id"), primary_key=True, sort_order=-2)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id, sort_order=-1)


def is_tenant_owned(model: type) -> bool:
    return bool(getattr(model, "__tenant_owned__", False))
