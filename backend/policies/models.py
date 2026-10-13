"""Policy versions, frozen input snapshots, evaluations and findings.

Published policy versions, snapshots, evaluations, findings and resolutions are
append-only. A correction produces a new snapshot and evaluation; history is
never rewritten to manufacture a pass.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.persistence.base import Base, TenantMixin, TimestampMixin


class PolicyLifecycle:
    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class PolicyVersion(TenantMixin, TimestampMixin, Base):
    __tablename__ = "policy_version"
    __table_args__ = (UniqueConstraint("organization_id", "policy_code", "version"),)

    policy_code: Mapped[str] = mapped_column(String(60))
    version: Mapped[int]
    module: Mapped[str] = mapped_column(String(40))
    document: Mapped[dict[str, Any]]
    digest: Mapped[str] = mapped_column(String(80))
    lifecycle: Mapped[str] = mapped_column(String(20), default=PolicyLifecycle.DRAFT)
    author_subject: Mapped[str] = mapped_column(String(200))
    publisher_subject: Mapped[str | None] = mapped_column(String(200))
    validation_errors: Mapped[list[Any]] = mapped_column(default=list)
    publish_reason: Mapped[str | None] = mapped_column(String(1000))
    published_at: Mapped[datetime | None]
    retired_at: Mapped[datetime | None]


class InputSnapshot(TenantMixin, TimestampMixin, Base):
    __tablename__ = "input_snapshot"
    __append_only__ = True

    schema_version: Mapped[int] = mapped_column(default=1)
    module: Mapped[str] = mapped_column(String(40))
    canonical_inputs: Mapped[dict[str, Any]]
    digest: Mapped[str] = mapped_column(String(80))
    source_revision_map: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Evaluation(TenantMixin, TimestampMixin, Base):
    __tablename__ = "evaluation"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "case_id"], ["case_record.organization_id", "case_record.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "snapshot_id"],
            ["input_snapshot.organization_id", "input_snapshot.id"],
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_version_id"],
            ["policy_version.organization_id", "policy_version.id"],
        ),
        Index("ix_evaluation_case", "organization_id", "case_id", "created_at"),
    )

    case_id: Mapped[uuid.UUID]
    proposal_id: Mapped[uuid.UUID | None]
    kind: Mapped[str] = mapped_column(String(20))  # DOCUMENT | ACTION
    snapshot_id: Mapped[uuid.UUID]
    input_digest: Mapped[str] = mapped_column(String(80))
    policy_version_id: Mapped[uuid.UUID]
    policy_digest: Mapped[str] = mapped_column(String(80))
    engine_version: Mapped[str] = mapped_column(String(40))
    case_revision: Mapped[int]
    outcome: Mapped[str] = mapped_column(String(20))
    coverage: Mapped[dict[str, Any]] = mapped_column(default=dict)
    explanation: Mapped[str | None] = mapped_column(String(4000))
    created_by: Mapped[str] = mapped_column(String(200))


class Finding(TenantMixin, Base):
    __tablename__ = "finding"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "evaluation_id"],
            ["evaluation.organization_id", "evaluation.id"],
        ),
    )

    evaluation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    rule_code: Mapped[str] = mapped_column(String(80))
    rule_version: Mapped[int]
    title: Mapped[str] = mapped_column(String(200))
    result: Mapped[str] = mapped_column(String(20))
    effect: Mapped[str | None] = mapped_column(String(20))
    severity: Mapped[str] = mapped_column(String(20))
    reason_code: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(String(1000))
    observed: Mapped[dict[str, Any]] = mapped_column(default=dict)
    expected: Mapped[dict[str, Any]] = mapped_column(default=dict)
    requires_review: Mapped[bool]


class FindingEvidence(TenantMixin, Base):
    __tablename__ = "finding_evidence"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "finding_id"], ["finding.organization_id", "finding.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "evidence_item_id"],
            ["evidence_item.organization_id", "evidence_item.id"],
        ),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(index=True)
    evidence_item_id: Mapped[uuid.UUID]


class FindingResolution(TenantMixin, TimestampMixin, Base):
    __tablename__ = "finding_resolution"
    __append_only__ = True
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "finding_id"], ["finding.organization_id", "finding.id"]
        ),
    )

    finding_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_subject: Mapped[str] = mapped_column(String(200))
    resolution_code: Mapped[str] = mapped_column(String(60))
    reason: Mapped[str] = mapped_column(String(1000))
    expires_at: Mapped[datetime | None]
