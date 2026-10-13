"""The verified actor behind a request or job."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from backend.errors import Forbidden
from backend.identity.roles import Capability


@dataclass(frozen=True)
class Actor:
    subject: str
    organization_id: uuid.UUID
    actor_type: str  # "user" | "service"
    principal_id: uuid.UUID  # membership or service-account id
    roles: tuple[str, ...] = ()
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    authorization_revision: int = 0
    approval_limit_minor: int | None = None
    display_name: str = ""

    @property
    def is_human(self) -> bool:
        return self.actor_type == "user"

    def can(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def require(self, capability: Capability) -> None:
        if not self.can(capability):
            raise Forbidden(
                f"Missing permission '{capability.value}'",
                code="PERMISSION_DENIED",
                details={"capability": capability.value},
            )


SYSTEM_SUBJECT = "system:worker"


def system_actor(organization_id: uuid.UUID) -> Actor:
    """Actor used by the worker for jobs it runs on an organization's behalf."""
    return Actor(
        subject=SYSTEM_SUBJECT,
        organization_id=organization_id,
        actor_type="system",
        principal_id=uuid.UUID(int=0),
        display_name="FinGuard worker",
    )
