from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from apps.api.deps import get_runtime, require, tenant_tx
from backend.identity.actor import Actor
from backend.identity.roles import Capability
from backend.policies import engine
from backend.policies import service as policies
from backend.policies.models import PolicyVersion
from backend.runtime import Runtime

router = APIRouter(prefix="/v1", tags=["policies"])


class PolicyOut(BaseModel):
    id: uuid.UUID
    policy_code: str
    version: int
    module: str
    lifecycle: str
    digest: str
    author_subject: str
    publisher_subject: str | None
    validation_errors: list[Any]
    published_at: datetime | None
    retired_at: datetime | None
    document: dict[str, Any]

    @classmethod
    def of(cls, p: PolicyVersion) -> PolicyOut:
        return cls.model_validate(p, from_attributes=True)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DraftIn(Strict):
    document: dict[str, Any]


class PublishIn(Strict):
    reason: str = Field(min_length=3, max_length=1000)


class SimulateIn(Strict):
    inputs: dict[str, Any]


class ResolutionIn(Strict):
    resolution_code: str = Field(pattern=r"^[A-Z_]{3,60}$")
    reason: str = Field(min_length=3, max_length=1000)


@router.get("/rules")
def rule_catalog(module: str | None = None):
    return [
        {
            "code": s.code,
            "version": s.version,
            "module": s.module,
            "title": s.title,
            "severity": s.severity.value,
            "parameters_schema": s.params.model_json_schema(),
        }
        for s in engine.catalog(module)
    ]


@router.get("/policies", response_model=list[PolicyOut])
def list_policies(
    actor: Actor = Depends(require(Capability.CASE_READ)), rt: Runtime = Depends(get_runtime)
):
    with tenant_tx(rt.db, actor) as tx:
        rows = tx.scalars(
            tx.select(PolicyVersion).order_by(PolicyVersion.policy_code, PolicyVersion.version)
        )
        return [PolicyOut.of(p) for p in rows]


@router.get("/policies/{policy_id}", response_model=PolicyOut)
def get_policy(
    policy_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.CASE_READ)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return PolicyOut.of(policies.get_policy(tx, policy_id))


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_draft(
    body: DraftIn,
    actor: Actor = Depends(require(Capability.POLICY_AUTHOR)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return PolicyOut.of(policies.create_draft(tx, actor, body.document))


@router.post("/policies/{policy_id}/validate", response_model=PolicyOut)
def validate_policy(
    policy_id: uuid.UUID,
    actor: Actor = Depends(require(Capability.POLICY_AUTHOR)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return PolicyOut.of(policies.validate(tx, actor, policy_id))


@router.post("/policies/{policy_id}/publish", response_model=PolicyOut, status_code=201)
def publish_policy(
    policy_id: uuid.UUID,
    body: PublishIn,
    actor: Actor = Depends(require(Capability.POLICY_PUBLISH)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        return PolicyOut.of(policies.publish(tx, actor, policy_id, body.reason))


@router.post("/policies/{policy_id}/simulate")
def simulate_policy(
    policy_id: uuid.UUID,
    body: SimulateIn,
    actor: Actor = Depends(require(Capability.POLICY_AUTHOR)),
    rt: Runtime = Depends(get_runtime),
):
    """Dry-run a policy version against sample inputs. Nothing is stored."""
    with tenant_tx(rt.db, actor) as tx:
        doc = policies.document_of(policies.get_policy(tx, policy_id))
    result = engine.evaluate(doc, policies.freeze_inputs(body.inputs))
    return {
        "outcome": result.outcome.value,
        "coverage": result.coverage,
        "findings": [
            {
                "rule_code": f.rule_code,
                "result": f.result.value,
                "effect": f.effect,
                "reason_code": f.reason_code,
                "message": f.message,
                "observed": policies.freeze_inputs(f.observed),
                "expected": policies.freeze_inputs(f.expected),
            }
            for f in result.findings
        ],
    }


@router.post("/findings/{finding_id}/resolutions", status_code=201)
def resolve_finding(
    finding_id: uuid.UUID,
    body: ResolutionIn,
    actor: Actor = Depends(require(Capability.FINDING_RESOLVE)),
    rt: Runtime = Depends(get_runtime),
):
    with tenant_tx(rt.db, actor) as tx:
        resolution = policies.resolve_finding(
            tx, actor, finding_id, resolution_code=body.resolution_code, reason=body.reason
        )
        return {
            "id": str(resolution.id),
            "finding_id": str(resolution.finding_id),
            "resolution_code": resolution.resolution_code,
            "actor_subject": resolution.actor_subject,
        }
