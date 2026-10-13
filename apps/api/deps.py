"""Request dependencies: database, authentication and authorization."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from fastapi import Depends, Header, Request

from backend.adapters.oidc.verifier import OidcVerifier
from backend.config import Settings
from backend.errors import InvalidInput, Unauthenticated
from backend.identity import service as identity
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.persistence.database import Database, TenantSession
from backend.runtime import Runtime


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_runtime(request: Request) -> Runtime:
    return request.app.state.runtime


def get_db(request: Request) -> Database:
    return request.app.state.db


def _verifier(request: Request) -> OidcVerifier | None:
    return getattr(request.app.state, "oidc_verifier", None)


def authenticated_subject(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
) -> str:
    """Return the verified subject of a human caller (not service accounts)."""
    settings = get_settings(request)
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
        verifier = _verifier(request)
        if verifier is None:
            raise Unauthenticated("Bearer tokens are not configured", code="INVALID_TOKEN")
        return verifier.verify(token)
    if x_dev_user and settings.dev_identity_enabled:
        return x_dev_user.strip()
    raise Unauthenticated("Authentication required")


def _parse_org(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        raise InvalidInput("X-Organization-Id must be a UUID") from None


def current_actor(
    request: Request,
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
    x_organization_id: str | None = Header(default=None),
) -> Actor:
    db = get_db(request)
    if authorization and authorization.lower().startswith(
        "bearer " + identity.SERVICE_TOKEN_PREFIX
    ):
        actor = identity.resolve_service(db, authorization[7:].strip())
        org = _parse_org(x_organization_id)
        if org is not None and org != actor.organization_id:
            raise Unauthenticated("Service credential is bound to another organization")
        return actor
    subject = authenticated_subject(request, authorization, x_dev_user)
    return identity.resolve_user(db, subject, _parse_org(x_organization_id))


def require(capability: Capability) -> Callable[..., Actor]:
    def dependency(actor: Actor = Depends(current_actor)) -> Actor:
        actor.require(capability)
        return actor

    return dependency


@contextmanager
def tenant_tx(db: Database, actor: Actor) -> Iterator[TenantSession]:
    with db.tenant(actor.organization_id, subject=actor.subject, actor=actor) as tx:
        yield tx
