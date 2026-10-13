"""Organizations (tenants)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import new_id, utcnow
from backend.persistence.base import Base


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
