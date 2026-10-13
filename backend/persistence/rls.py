"""Database-level guards applied by migrations.

PostgreSQL:
* ``app_runtime`` is a NOLOGIN role without BYPASSRLS; deployments grant it to
  the application's login user. It never owns tables.
* Every tenant-owned table gets ``FORCE ROW LEVEL SECURITY`` and a policy on
  ``current_setting('app.organization_id')``.
* Append-only tables (audit, decisions) receive INSERT/SELECT grants only and a
  trigger rejecting UPDATE/DELETE.

SQLite gets the append-only triggers so local development behaves the same.
"""

from __future__ import annotations

from alembic import op

ORG_SETTING = "nullif(current_setting('app.organization_id', true), '')::uuid"
SUBJECT_SETTING = "nullif(current_setting('app.identity_subject', true), '')"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def ensure_runtime_role() -> None:
    if not _is_postgres():
        return
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            CREATE ROLE app_runtime NOLOGIN NOBYPASSRLS;
          END IF;
        END $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO app_runtime")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION finguard_reject_mutation() RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'table % is append-only', TG_TABLE_NAME
            USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def tenant_table(table: str, *, append_only: bool = False, deletable: bool = False) -> None:
    """Enable RLS and grants for a tenant-owned table."""
    if _is_postgres():
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant ON {table} TO app_runtime "
            f"USING (organization_id = {ORG_SETTING}) "
            f"WITH CHECK (organization_id = {ORG_SETTING})"
        )
        grants = "SELECT, INSERT" if append_only else "SELECT, INSERT, UPDATE"
        if deletable and not append_only:
            grants += ", DELETE"
        op.execute(f"GRANT {grants} ON {table} TO app_runtime")
    if append_only:
        append_only_table(table)


def append_only_table(table: str) -> None:
    if _is_postgres():
        op.execute(
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION finguard_reject_mutation()"
        )
    else:
        for verb in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER {table}_no_{verb.lower()} BEFORE {verb} ON {table} "
                f"BEGIN SELECT RAISE(ABORT, '{table} is append-only'); END"
            )


def system_table(table: str, grants: str = "SELECT, INSERT, UPDATE") -> None:
    """Untenanted metadata tables (job queue, outbox): plain grants, no RLS."""
    if _is_postgres():
        op.execute(f"GRANT {grants} ON {table} TO app_runtime")


def raw(sql_pg: str) -> None:
    if _is_postgres():
        op.execute(sql_pg)
