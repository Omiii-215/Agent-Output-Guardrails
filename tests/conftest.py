"""Shared test fixtures.

Integration tests run against real PostgreSQL by default: either
``FINGUARD_TEST_DATABASE_URL`` (owner URL, e.g. a CI service container) or an
embedded server started through ``pgserver``. Set ``FINGUARD_TEST_BACKEND=sqlite``
to run the same tests on SQLite without row-level security.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import text

from backend.identity.models import Organization
from backend.persistence.database import Database
from backend.persistence.embedded import PostgresUrls, create_database, migrate
from backend.persistence.models import metadata
from tests.support import BACKEND


@pytest.fixture(scope="session")
def pg_urls() -> Iterator[PostgresUrls | None]:
    if BACKEND == "sqlite":
        yield None
        return
    yield create_database(f"finguard_test_{os.getpid()}")


@pytest.fixture
def db(pg_urls: PostgresUrls | None, tmp_path: Path) -> Iterator[Database]:
    if pg_urls is None:
        url = f"sqlite:///{tmp_path / 'finguard.sqlite3'}"
        migrate(url)
        database = Database(url)
    else:
        database = Database(pg_urls.runtime, admin_url=pg_urls.admin)
    try:
        yield database
    finally:
        if database.is_postgres:
            tables = ", ".join(t.name for t in metadata.sorted_tables)
            with database.admin_engine.begin() as conn:
                conn.execute(text(f"TRUNCATE {tables} CASCADE"))
        database.dispose()


def make_org(db: Database, name: str) -> uuid.UUID:
    with db.admin() as session:
        org = Organization(name=name, legal_entity_reference=f"{name}-LE")
        session.add(org)
        session.flush()
        return org.id


@pytest.fixture
def two_orgs(db: Database) -> tuple[uuid.UUID, uuid.UUID]:
    """At least two synthetic organizations for every isolation test."""
    return make_org(db, "Acme Distributors"), make_org(db, "Globex Wholesale")
