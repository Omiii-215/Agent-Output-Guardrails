from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import authenticated_subject, current_actor, get_db, require, tenant_tx
from backend.identity import service as identity
from backend.identity.actor import Actor
from backend.identity.models import Membership
from backend.identity.roles import Capability
from backend.persistence.database import Database

router = APIRouter(prefix="/v1", tags=["identity"])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MemberOut(BaseModel):
    id: uuid.UUID
    identity_subject: str
    display_name: str
    roles: list[str]
    status: str
    approval_limit_minor: str | None
    authorization_revision: int

    @classmethod
    def of(cls, m: Membership) -> MemberOut:
        return cls(
            id=m.id,
            identity_subject=m.identity_subject,
            display_name=m.display_name,
            roles=list(m.roles),
            status=m.status,
            approval_limit_minor=(
                str(m.approval_limit_minor) if m.approval_limit_minor is not None else None
            ),
            authorization_revision=m.authorization_revision,
        )


class MemberCreate(StrictModel):
    subject: str = Field(min_length=3, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    roles: list[str]
    approval_limit_minor: int | None = Field(default=None, ge=0)


class MemberUpdate(StrictModel):
    roles: list[str] | None = None
    status: str | None = None
    approval_limit_minor: int | None = Field(default=None, ge=0)
    reason: str = Field(min_length=3, max_length=1000)


class ServiceAccountCreate(StrictModel):
    name: str = Field(min_length=1, max_length=200)
    scopes: list[str]
    expires_at: datetime | None = None


@router.get("/me")
def me(subject: str = Depends(authenticated_subject), db: Database = Depends(get_db)):
    return {
        "subject": subject,
        "memberships": [
            {
                "organization_id": str(m.organization_id),
                "organization_name": m.organization_name,
                "roles": m.roles,
            }
            for m in identity.memberships_for(db, subject)
        ],
    }


@router.get("/session")
def session(actor: Actor = Depends(current_actor)):
    return {
        "subject": actor.subject,
        "display_name": actor.display_name,
        "organization_id": str(actor.organization_id),
        "actor_type": actor.actor_type,
        "roles": list(actor.roles),
        "capabilities": sorted(c.value for c in actor.capabilities),
    }


@router.get("/members", response_model=list[MemberOut])
def list_members(
    actor: Actor = Depends(require(Capability.MEMBER_MANAGE)), db: Database = Depends(get_db)
):
    with tenant_tx(db, actor) as tx:
        return [MemberOut.of(m) for m in identity.list_members(tx)]


@router.post("/members", response_model=MemberOut, status_code=201)
def add_member(
    body: MemberCreate,
    actor: Actor = Depends(require(Capability.MEMBER_MANAGE)),
    db: Database = Depends(get_db),
):
    with tenant_tx(db, actor) as tx:
        member = identity.add_member(
            tx,
            actor,
            subject=body.subject,
            display_name=body.display_name,
            roles=body.roles,
            approval_limit_minor=body.approval_limit_minor,
        )
        return MemberOut.of(member)


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(
    member_id: uuid.UUID,
    body: MemberUpdate,
    actor: Actor = Depends(require(Capability.MEMBER_MANAGE)),
    db: Database = Depends(get_db),
):
    with tenant_tx(db, actor) as tx:
        member = identity.update_member(
            tx,
            actor,
            member_id,
            roles=body.roles,
            status=body.status,
            approval_limit_minor=body.approval_limit_minor,
            reason=body.reason,
        )
        return MemberOut.of(member)


@router.post("/service-accounts", status_code=201)
def create_service_account(
    body: ServiceAccountCreate,
    actor: Actor = Depends(require(Capability.MEMBER_MANAGE)),
    db: Database = Depends(get_db),
):
    with tenant_tx(db, actor) as tx:
        account, token = identity.create_service_account(
            tx, actor, name=body.name, scopes=body.scopes, expires_at=body.expires_at
        )
        return {"id": str(account.id), "scopes": account.scopes, "token": token}
