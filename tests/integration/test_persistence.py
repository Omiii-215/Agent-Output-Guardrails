import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.errors import NotFound
from backend.persistence.models import metadata
from backend.telemetry import audit
from backend.telemetry.audit import AuditEvent
from tests.support import pg_only


def test_migrations_match_models(db):
    with db.admin_engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn), metadata)
    assert diffs == []


def test_audit_events_are_append_only(db, two_orgs):
    org_a, _ = two_orgs
    with db.tenant(org_a) as tx:
        event = audit.record(tx, "case.created", object_type="case", object_id=uuid.uuid4())
    with pytest.raises(DBAPIError), db.tenant(org_a) as tx:
        tx.session.execute(
            text("UPDATE audit_event SET action = 'tampered' WHERE id = :id"), {"id": event.id}
        )
    with pytest.raises(DBAPIError), db.tenant(org_a) as tx:
        tx.session.execute(text("DELETE FROM audit_event WHERE id = :id"), {"id": event.id})


def test_audit_digest_and_trace(db, two_orgs):
    org_a, _ = two_orgs
    with db.tenant(org_a) as tx:
        event = audit.record(
            tx, "policy.published", object_type="policy", object_id=None, data={"v": 3}
        )
    assert event.change_digest.startswith("sha256:")
    assert event.occurred_at.tzinfo is not None


def test_tenant_session_scopes_reads_and_writes(db, two_orgs):
    org_a, org_b = two_orgs
    with db.tenant(org_a) as tx:
        event = audit.record(tx, "x", object_type="case", object_id=None)
    with db.tenant(org_b) as tx, pytest.raises(NotFound):
        tx.get(AuditEvent, event.id)
    with db.tenant(org_b) as tx, pytest.raises(NotFound):
        tx.add(AuditEvent(organization_id=org_a, actor_type="user", actor_id="x"))


@pg_only
def test_row_level_security_hides_other_tenants_even_for_raw_sql(db, two_orgs):
    org_a, org_b = two_orgs
    with db.tenant(org_a) as tx:
        audit.record(tx, "a-only", object_type="case", object_id=None)
    with db.tenant(org_b) as tx:
        rows = tx.session.execute(text("SELECT action FROM audit_event")).all()
    assert rows == []
    with db.system() as session:
        assert session.execute(text("SELECT count(*) FROM audit_event")).scalar() == 0


@pg_only
def test_row_level_security_rejects_cross_tenant_insert(db, two_orgs):
    org_a, org_b = two_orgs
    with pytest.raises(DBAPIError), db.tenant(org_a) as tx:
        tx.session.execute(
            text(
                "INSERT INTO audit_event (organization_id, id, actor_type, actor_id, action,"
                " object_type, data, change_digest, simulated, occurred_at)"
                " VALUES (:org, :id, 'user', 'u', 'x', 'case', '{}', 'd', false, now())"
            ),
            {"org": org_b, "id": uuid.uuid4()},
        )


@pg_only
def test_runtime_role_is_not_owner_and_cannot_bypass_rls(db):
    with db.system() as session:
        row = session.execute(
            text("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
        ).one()
        owner = session.execute(
            text("SELECT tableowner FROM pg_tables WHERE tablename = 'audit_event'")
        ).scalar()
        me = session.execute(text("SELECT current_user")).scalar()
    assert row == (False, False)
    assert owner != me
