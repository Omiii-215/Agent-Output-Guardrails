"""Membership resolution and administration.

Membership is checked on every request, so revocation and role changes take
effect immediately (story P-07). Administrators manage members but cannot
change their own roles, which stops an admin granting themselves approval.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from backend.domain.clock import ensure_aware, utcnow
from backend.errors import Conflict, Forbidden, InvalidInput, NotFound, Unauthenticated
from backend.identity.actor import Actor
from backend.identity.models import Membership, Organization, ServiceAccount
from backend.identity.roles import SERVICE_SCOPES, Capability, capabilities_for, validate_roles
from backend.persistence.database import Database, TenantSession
from backend.telemetry import audit

SERVICE_TOKEN_PREFIX = "fgsa_"


@dataclass(frozen=True)
class MembershipSummary:
    organization_id: uuid.UUID
    organization_name: str
    roles: list[str]
    status: str


def _actor_from_membership(m: Membership) -> Actor:
    return Actor(
        subject=m.identity_subject,
        organization_id=m.organization_id,
        actor_type="user",
        principal_id=m.id,
        roles=tuple(m.roles),
        capabilities=capabilities_for(list(m.roles)),
        authorization_revision=m.authorization_revision,
        approval_limit_minor=m.approval_limit_minor,
        display_name=m.display_name,
    )


def memberships_for(db: Database, subject: str) -> list[MembershipSummary]:
    with db.identity(subject) as session:
        rows = session.execute(
            select(Membership, Organization.name)
            .join(Organization, Organization.id == Membership.organization_id)
            .where(Membership.identity_subject == subject, Membership.status == "ACTIVE")
            .order_by(Organization.name)
        ).all()
    return [MembershipSummary(m.organization_id, name, list(m.roles), m.status) for m, name in rows]


def resolve_user(db: Database, subject: str, organization_id: uuid.UUID | None) -> Actor:
    with db.identity(subject) as session:
        stmt = select(Membership).where(
            Membership.identity_subject == subject, Membership.status == "ACTIVE"
        )
        if organization_id is not None:
            stmt = stmt.where(Membership.organization_id == organization_id)
        found = session.scalars(stmt).all()
    if not found:
        raise NotFound("Organization not found", code="ORGANIZATION_NOT_FOUND")
    if len(found) > 1:
        raise InvalidInput(
            "Select an organization with the X-Organization-Id header",
            code="ORGANIZATION_REQUIRED",
        )
    return _actor_from_membership(found[0])


def _hash_secret(token: str) -> str:
    return "sha256:" + hashlib.sha256(token.encode()).hexdigest()


def resolve_service(db: Database, token: str) -> Actor:
    if not token.startswith(SERVICE_TOKEN_PREFIX):
        raise Unauthenticated("Invalid service credential", code="INVALID_TOKEN")
    credential_hash = _hash_secret(token)
    # The identity context for a service lookup is its credential hash.
    with db.identity(credential_hash) as session:
        account = session.scalars(
            select(ServiceAccount).where(ServiceAccount.credential_hash == credential_hash)
        ).first()
    now = utcnow()
    if (
        account is None
        or account.revoked_at is not None
        or (account.expires_at is not None and ensure_aware(account.expires_at) <= now)
    ):
        raise Unauthenticated("Invalid service credential", code="INVALID_TOKEN")
    scopes = frozenset(Capability(s) for s in account.scopes) & SERVICE_SCOPES
    return Actor(
        subject=f"service:{account.id}",
        organization_id=account.organization_id,
        actor_type="service",
        principal_id=account.id,
        capabilities=scopes,
        display_name=account.name,
    )


# -- administration ----------------------------------------------------------


def list_members(tx: TenantSession) -> list[Membership]:
    return list(tx.scalars(tx.select(Membership).order_by(Membership.display_name)))


def add_member(
    tx: TenantSession,
    actor: Actor,
    *,
    subject: str,
    display_name: str,
    roles: list[str],
    approval_limit_minor: int | None = None,
) -> Membership:
    actor.require(Capability.MEMBER_MANAGE)
    try:
        roles = validate_roles(roles)
    except ValueError as exc:
        raise InvalidInput(str(exc), code="UNKNOWN_ROLE") from None
    existing = tx.first(tx.select(Membership).where(Membership.identity_subject == subject))
    if existing is not None:
        raise Conflict("Identity is already a member", code="MEMBER_EXISTS")
    member = tx.add(
        Membership(
            identity_subject=subject,
            display_name=display_name,
            roles=roles,
            approval_limit_minor=approval_limit_minor,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "member.added",
        object_type="membership",
        object_id=member.id,
        data={"subject": subject, "roles": roles},
    )
    return member


def update_member(
    tx: TenantSession,
    actor: Actor,
    member_id: uuid.UUID,
    *,
    roles: list[str] | None = None,
    status: str | None = None,
    approval_limit_minor: int | None = None,
    reason: str,
) -> Membership:
    actor.require(Capability.MEMBER_MANAGE)
    member = tx.get(Membership, member_id, for_update=True)
    if member.identity_subject == actor.subject and roles is not None:
        raise Forbidden("Administrators cannot change their own roles", code="SELF_ROLE_CHANGE")
    changes: dict[str, object] = {}
    if roles is not None:
        try:
            member.roles = validate_roles(roles)
        except ValueError as exc:
            raise InvalidInput(str(exc), code="UNKNOWN_ROLE") from None
        changes["roles"] = member.roles
    if status is not None:
        if status not in ("ACTIVE", "REVOKED"):
            raise InvalidInput("Status must be ACTIVE or REVOKED")
        member.status = status
        changes["status"] = status
    if approval_limit_minor is not None:
        member.approval_limit_minor = approval_limit_minor
        changes["approval_limit_minor"] = str(approval_limit_minor)
    if changes:
        member.authorization_revision += 1
        audit.record(
            tx,
            "member.updated",
            object_type="membership",
            object_id=member.id,
            reason=reason,
            data={**changes, "authorization_revision": member.authorization_revision},
        )
    return member


def create_service_account(
    tx: TenantSession,
    actor: Actor,
    *,
    name: str,
    scopes: list[str],
    expires_at: datetime | None,
) -> tuple[ServiceAccount, str]:
    """Create a machine actor. The secret is returned once and stored only as a hash."""
    actor.require(Capability.MEMBER_MANAGE)
    try:
        requested = {Capability(s) for s in scopes}
    except ValueError as exc:
        raise InvalidInput(str(exc), code="UNKNOWN_SCOPE") from None
    if not requested <= SERVICE_SCOPES:
        raise InvalidInput(
            "Service accounts cannot hold these scopes",
            code="SCOPE_NOT_ALLOWED",
            details=sorted(s.value for s in requested - SERVICE_SCOPES),
        )
    token = SERVICE_TOKEN_PREFIX + secrets.token_urlsafe(32)
    account = tx.add(
        ServiceAccount(
            name=name,
            credential_hash=_hash_secret(token),
            scopes=sorted(s.value for s in requested),
            expires_at=expires_at,
            created_by=actor.subject,
        )
    )
    tx.flush()
    audit.record(
        tx,
        "service_account.created",
        object_type="service_account",
        object_id=account.id,
        data={"scopes": account.scopes},
    )
    return account, token
