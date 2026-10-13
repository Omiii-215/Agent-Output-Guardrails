"""Development and test helpers for a real PostgreSQL database.

Uses ``FINGUARD_TEST_DATABASE_URL`` (an owner/superuser URL) when provided,
otherwise starts an embedded PostgreSQL through the optional ``pgserver``
development dependency. Never imported by the API or worker at runtime.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

RUNTIME_LOGIN = "finguard_app"
ROOT = Path(__file__).resolve().parents[2]

_server = None  # keep the embedded server alive for the process


@dataclass(frozen=True)
class PostgresUrls:
    admin: str
    runtime: str


def _with_driver(url: URL) -> URL:
    return url.set(drivername="postgresql+psycopg")


def server_admin_url(data_dir: Path | None = None) -> URL:
    global _server
    explicit = os.environ.get("FINGUARD_TEST_DATABASE_URL")
    if explicit:
        return _with_driver(make_url(explicit))
    import pgserver  # development dependency

    if _server is None:
        directory = data_dir or Path(tempfile.mkdtemp(prefix="finguard-pg-"))
        _server = pgserver.get_server(directory, cleanup_mode="stop")
    return _with_driver(make_url(_server.get_uri()))


def alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    return cfg


def migrate(url: str, revision: str = "head") -> None:
    engine = create_engine(url)
    with engine.begin() as conn:
        cfg = alembic_config()
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, revision)
    engine.dispose()


def create_database(name: str, data_dir: Path | None = None) -> PostgresUrls:
    """(Re)create a database, migrate it and return owner + runtime URLs."""
    server = server_admin_url(data_dir)
    engine = create_engine(server, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    engine.dispose()

    admin = server.set(database=name)
    admin_str = admin.render_as_string(hide_password=False)
    migrate(admin_str)

    engine = create_engine(admin, isolation_level="AUTOCOMMIT")
    with engine.connect() as conn:
        if not conn.execute(text("SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime'")).first():
            engine.dispose()
            return PostgresUrls(admin=admin_str, runtime=admin_str)  # before first migration
        exists = conn.execute(
            text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": RUNTIME_LOGIN}
        ).first()
        if not exists:
            conn.execute(text(f"CREATE ROLE {RUNTIME_LOGIN} LOGIN PASSWORD 'finguard' NOBYPASSRLS"))
        conn.execute(text(f"GRANT app_runtime TO {RUNTIME_LOGIN}"))
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{name}" TO {RUNTIME_LOGIN}'))
    engine.dispose()

    runtime = admin.set(username=RUNTIME_LOGIN, password="finguard")
    return PostgresUrls(admin=admin_str, runtime=runtime.render_as_string(hide_password=False))
