"""Roles and the capabilities they grant (LLD §8, flows §4).

Roles grant distinct capabilities. Being an administrator does not grant
financial approval, and no role implies another.
"""

from __future__ import annotations

from enum import StrEnum


class Role(StrEnum):
    ORG_ADMIN = "org_admin"
    POLICY_AUTHOR = "policy_author"
    POLICY_PUBLISHER = "policy_publisher"
    FINANCE_OPERATOR = "finance_operator"
    FINANCE_APPROVER = "finance_approver"
    COMPLIANCE_REVIEWER = "compliance_reviewer"
    AUDITOR = "auditor"


class Capability(StrEnum):
    CASE_READ = "case.read"
    CASE_WRITE = "case.write"
    DOCUMENT_UPLOAD = "document.upload"
    EVALUATION_RUN = "evaluation.run"
    FINDING_RESOLVE = "finding.resolve"
    VENDOR_WRITE = "vendor.write"
    BENEFICIARY_VERIFY = "beneficiary.verify"
    PROPOSAL_CREATE = "proposal.create"
    APPROVAL_REQUEST = "approval.request"
    APPROVAL_DECIDE = "approval.decide"
    INTENT_CREATE = "intent.create"
    ACTION_HALT = "action.halt"
    RECON_IMPORT = "reconciliation.import"
    RECON_MATCH_APPROVE = "reconciliation.match_approve"
    POLICY_AUTHOR = "policy.author"
    POLICY_PUBLISH = "policy.publish"
    AUDIT_READ = "audit.read"
    AUDIT_EXPORT = "audit.export"
    MEMBER_MANAGE = "member.manage"
    OPERATIONS_READ = "operations.read"


ROLE_CAPABILITIES: dict[Role, frozenset[Capability]] = {
    Role.ORG_ADMIN: frozenset(
        {Capability.MEMBER_MANAGE, Capability.OPERATIONS_READ, Capability.ACTION_HALT}
    ),
    Role.POLICY_AUTHOR: frozenset({Capability.POLICY_AUTHOR, Capability.CASE_READ}),
    Role.POLICY_PUBLISHER: frozenset({Capability.POLICY_PUBLISH, Capability.CASE_READ}),
    Role.FINANCE_OPERATOR: frozenset(
        {
            Capability.CASE_READ,
            Capability.CASE_WRITE,
            Capability.DOCUMENT_UPLOAD,
            Capability.EVALUATION_RUN,
            Capability.VENDOR_WRITE,
            Capability.PROPOSAL_CREATE,
            Capability.APPROVAL_REQUEST,
            Capability.INTENT_CREATE,
            Capability.RECON_IMPORT,
            Capability.RECON_MATCH_APPROVE,
        }
    ),
    Role.FINANCE_APPROVER: frozenset(
        {
            Capability.CASE_READ,
            Capability.EVALUATION_RUN,
            Capability.FINDING_RESOLVE,
            Capability.BENEFICIARY_VERIFY,
            Capability.APPROVAL_DECIDE,
            Capability.ACTION_HALT,
            Capability.RECON_MATCH_APPROVE,
            Capability.AUDIT_READ,
            Capability.AUDIT_EXPORT,
        }
    ),
    Role.COMPLIANCE_REVIEWER: frozenset(
        {Capability.CASE_READ, Capability.FINDING_RESOLVE, Capability.AUDIT_READ}
    ),
    Role.AUDITOR: frozenset({Capability.CASE_READ, Capability.AUDIT_READ, Capability.AUDIT_EXPORT}),
}

# Scopes a machine actor may hold. Service accounts never approve.
SERVICE_SCOPES: frozenset[Capability] = frozenset(
    {
        Capability.CASE_READ,
        Capability.DOCUMENT_UPLOAD,
        Capability.PROPOSAL_CREATE,
        Capability.APPROVAL_REQUEST,
        Capability.RECON_IMPORT,
    }
)


def capabilities_for(roles: list[str]) -> frozenset[Capability]:
    caps: set[Capability] = set()
    for name in roles:
        caps |= ROLE_CAPABILITIES[Role(name)]
    return frozenset(caps)


def validate_roles(roles: list[str]) -> list[str]:
    unknown = [r for r in roles if r not in Role.__members__.values()]
    if unknown:
        raise ValueError(f"Unknown roles: {', '.join(unknown)}")
    return sorted(set(roles))
