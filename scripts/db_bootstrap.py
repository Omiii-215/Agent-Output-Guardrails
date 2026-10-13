"""Migrate the database with owner credentials and grant the runtime login.

    FINGUARD_DATABASE_ADMIN_URL=postgresql+psycopg://owner@db/finguard \
    FINGUARD_DATABASE_URL=postgresql+psycopg://finguard_app:...@db/finguard \
    PYTHONPATH=. uv run python scripts/db_bootstrap.py

The runtime login must already exist (created by the platform or
``infrastructure/postgres/init.sql``); it receives the NOLOGIN ``app_runtime``
role created by the migrations and never owns tables. For SQLite the script
only runs migrations.
"""

from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from backend.config import get_settings
from backend.persistence.embedded import migrate


def main() -> int:
    settings = get_settings()
    admin_url = settings.database_admin_url or settings.database_url
    migrate(admin_url)
    if not admin_url.startswith("postgresql"):
        print("migrated (sqlite)")
        return 0
    runtime_user = make_url(settings.database_url).username
    admin_user = make_url(admin_url).username
    if runtime_user and runtime_user != admin_user:
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as conn:
            conn.execute(text(f'GRANT app_runtime TO "{runtime_user}"'))
        engine.dispose()
        print(f"migrated; granted app_runtime to {runtime_user}")
    else:
        print("migrated; WARNING: runtime and owner credentials are the same")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
