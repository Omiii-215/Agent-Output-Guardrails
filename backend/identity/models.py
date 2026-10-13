"""Organizations (tenants), memberships and service accounts."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import new_id, utcnow
from backend.persistence.base import Base, TenantMixin, TimestampMixin


class Organization(Base):
    """One legal entity per tenant initially (blueprint §11)."""

    __tablename__ = "organization"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    legal_entity_reference: Mapped[str] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    base_currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    settings_revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Membership(TenantMixin, TimestampMixin, Base):
    """A verified identity's roles inside one organization.

    ``authorization_revision`` increases whenever roles, limits or status
    change; approvals record the revision they relied on.
    """

    __tablename__ = "membership"
    __table_args__ = (UniqueConstraint("organization_id", "identity_subject"),)

    identity_subject: Mapped[str] = mapped_column(String(200), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    roles: Mapped[list[Any]] = mapped_column(default=list)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")  # ACTIVE | REVOKED
    approval_limit_minor: Mapped[int | None] = mapped_column(BigInteger)
    authorization_revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class ServiceAccount(TenantMixin, TimestampMixin, Base):
    """Machine actor with explicit scopes. Never a human approver."""

    __tablename__ = "service_account"

    name: Mapped[str] = mapped_column(String(200))
    credential_hash: Mapped[str] = mapped_column(String(80), unique=True)
    scopes: Mapped[list[Any]] = mapped_column(default=list)
    expires_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    created_by: Mapped[str] = mapped_column(String(200))
