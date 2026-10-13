"""Alembic environment.

Migrations run with owner credentials (FINGUARD_DATABASE_ADMIN_URL, falling
back to FINGUARD_DATABASE_URL). Tests pass an open connection through
``config.attributes["connection"]``.
"""

from __future__ import annotations

from alembic import context

from backend.config import get_settings
from backend.persistence.database import make_engine
from backend.persistence.models import metadata

config = context.config


def _run(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=metadata,
        render_as_batch=connection.dialect.name == "sqlite",
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    settings = get_settings()
    url = (
        config.get_main_option("sqlalchemy.url")
        or settings.database_admin_url
        or settings.database_url
    )
    engine = make_engine(url)
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


run_migrations_online()
