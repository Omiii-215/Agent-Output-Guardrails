"""Autogenerate an Alembic migration against a fresh embedded PostgreSQL.

    PYTHONPATH=. uv run python scripts/new_migration.py "add cases"

Review the generated file and add ``rls.tenant_table(...)`` calls for every
new tenant-owned table before committing.
"""

from __future__ import annotations

import sys

from alembic import command

from backend.persistence.embedded import alembic_config, create_database


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    urls = create_database("finguard_migrations")
    cfg = alembic_config()
    cfg.set_main_option("sqlalchemy.url", urls.admin.replace("%", "%%"))
    command.revision(cfg, message=sys.argv[1], autogenerate=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
