"""Payment provider contract and the first-release simulator (ADR 0006).

Transport only: authorization, limits and approvals live in
``backend/actions``. The simulator persists its own provider-side ledger so it
behaves like a real provider across process restarts: idempotency keys replay,
a response can be lost after acceptance, statuses can be queried, and
settlement arrives later as a signed (possibly duplicated) webhook.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from sqlalchemy import BigInteger, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column

from backend.domain.clock import new_id, utcnow
from backend.persistence.base import Base
from backend.persistence.database import Database


class ProviderTimeout(RuntimeError):
    """No response. The provider may or may not have acted."""


@dataclass(frozen=True)
class FrozenAction:
    organization_id: uuid.UUID
    amount_minor: int
    currency: str
    beneficiary_fingerprint: str
    reference: str


@dataclass(frozen=True)
class SubmitResult:
    outcome: str  # ACCEPTED | FAILED
    provider_reference: str | None
    code: str


@dataclass(frozen=True)
class ProviderStatus:
    state: str  # NOT_FOUND | ACCEPTED | SETTLED | FAILED | REVERSED
    provider_reference: str | None


class PaymentAdapter(Protocol):
    name: str

    def submit(self, action: FrozenAction, idempotency_key: str) -> SubmitResult: ...
    def status(self, organization_id: uuid.UUID, idempotency_key: str) -> ProviderStatus: ...


class SimulatedTransfer(Base):
    """Provider-side record. Not application data; the app never trusts it directly."""

    __tablename__ = "simulator_transfer"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=new_id)
    organization_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organization.id"))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    request_hash: Mapped[str] = mapped_column(String(80))
    amount_minor: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3))
    state: Mapped[str] = mapped_column(String(20))
    reference: Mapped[str] = mapped_column(String(60))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


@dataclass
class SimulatedPaymentProvider:
    """Behaviour for the next submissions comes from ``plan`` (default ACCEPT):
    ACCEPT, REJECT, TIMEOUT_BEFORE (nothing recorded), TIMEOUT_AFTER (recorded,
    response lost)."""

    db: Database
    webhook_secret: str
    plan: list[str] = field(default_factory=list)
    name: str = "simulator"

    def _request_hash(self, action: FrozenAction) -> str:
        body = f"{action.amount_minor}|{action.currency}|{action.beneficiary_fingerprint}"
        return "sha256:" + hashlib.sha256(body.encode()).hexdigest()

    def submit(self, action: FrozenAction, idempotency_key: str) -> SubmitResult:
        behaviour = self.plan.pop(0) if self.plan else "ACCEPT"
        if behaviour == "TIMEOUT_BEFORE":
            raise ProviderTimeout("simulated timeout before acceptance")
        with self.db.system() as session:
            existing = session.scalars(
                select(SimulatedTransfer).where(
                    SimulatedTransfer.idempotency_key == idempotency_key
                )
            ).first()
            if existing is not None:  # idempotent replay
                if existing.request_hash != self._request_hash(action):
                    return SubmitResult("FAILED", None, "IDEMPOTENCY_KEY_REUSED")
                return SubmitResult(
                    "FAILED" if existing.state == "FAILED" else "ACCEPTED",
                    existing.reference,
                    "REPLAYED",
                )
            state = "FAILED" if behaviour == "REJECT" else "ACCEPTED"
            transfer = SimulatedTransfer(
                organization_id=action.organization_id,
                idempotency_key=idempotency_key,
                request_hash=self._request_hash(action),
                amount_minor=action.amount_minor,
                currency=action.currency,
                state=state,
                reference=f"SIM-{uuid.uuid4().hex[:12].upper()}",
            )
            session.add(transfer)
            reference = transfer.reference
        if behaviour == "TIMEOUT_AFTER":
            raise ProviderTimeout("simulated lost response after acceptance")
        if state == "FAILED":
            return SubmitResult("FAILED", reference, "BENEFICIARY_BANK_REJECTED")
        return SubmitResult("ACCEPTED", reference, "OK")

    def status(self, organization_id: uuid.UUID, idempotency_key: str) -> ProviderStatus:
        with self.db.system() as session:
            transfer = session.scalars(
                select(SimulatedTransfer).where(
                    SimulatedTransfer.idempotency_key == idempotency_key,
                    SimulatedTransfer.organization_id == organization_id,
                )
            ).first()
            if transfer is None:
                return ProviderStatus("NOT_FOUND", None)
            return ProviderStatus(transfer.state, transfer.reference)

    # -- provider-side events (used by tests and the development console) ----------

    def advance(self, organization_id: uuid.UUID, idempotency_key: str, state: str) -> dict:
        """Move a transfer to SETTLED/FAILED/REVERSED and return the webhook event."""
        with self.db.system() as session:
            transfer = session.scalars(
                select(SimulatedTransfer).where(
                    SimulatedTransfer.idempotency_key == idempotency_key,
                    SimulatedTransfer.organization_id == organization_id,
                )
            ).one()
            transfer.state = state
            return {
                "event_id": f"evt_{uuid.uuid4().hex}",
                "type": f"transfer.{state.lower()}",
                "organization_id": str(organization_id),
                "idempotency_key": idempotency_key,
                "provider_reference": transfer.reference,
                "occurred_at": utcnow().isoformat(),
            }

    def sign(self, body: bytes) -> str:
        return sign(self.webhook_secret, body)


def sign(secret: str, body: bytes) -> str:
    return "v1=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, header: str | None) -> bool:
    return bool(header) and hmac.compare_digest(sign(secret, body), header or "")


def encode_event(event: dict) -> bytes:
    return json.dumps(event, separators=(",", ":"), sort_keys=True).encode()
