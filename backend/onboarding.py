"""Tenant provisioning: create an organization and install policy templates.

Runs with owner credentials (seed scripts, onboarding tooling). Templates are a
starting point; the customer's policy owner reviews and republishes them.
"""

from __future__ import annotations

import uuid

from backend import bootstrap
from backend.actions.templates import PAYMENT_PREFLIGHT
from backend.identity.actor import system_actor
from backend.identity.models import Organization
from backend.modules.invoices.templates import INVOICE_PREFLIGHT
from backend.persistence.database import Database
from backend.policies import service as policies
from backend.policies.models import PolicyLifecycle, PolicyVersion

TEMPLATES = (INVOICE_PREFLIGHT, PAYMENT_PREFLIGHT)


def install_default_policies(db: Database, organization_id: uuid.UUID) -> None:
    bootstrap.load()
    with db.tenant(organization_id, actor=system_actor(organization_id)) as tx:
        for template in TEMPLATES:
            exists = tx.first(
                tx.select(PolicyVersion).where(
                    PolicyVersion.policy_code == template["policy_code"],
                    PolicyVersion.lifecycle == PolicyLifecycle.PUBLISHED,
                )
            )
            if exists is None:
                policies.install_template(tx, template)


def provision_organization(
    db: Database, *, name: str, legal_entity_reference: str, base_currency: str = "INR"
) -> uuid.UUID:
    with db.admin() as session:
        org = Organization(
            name=name, legal_entity_reference=legal_entity_reference, base_currency=base_currency
        )
        session.add(org)
        session.flush()
        org_id = org.id
    install_default_policies(db, org_id)
    return org_id
