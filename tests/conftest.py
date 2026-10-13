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
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import create_app
from backend.config import Settings
from backend.identity.models import Organization
from backend.persistence.database import Database
from backend.persistence.embedded import PostgresUrls, create_database, migrate
from backend.persistence.models import metadata
from tests.support import BACKEND, ApiClient, actor_for, add_member


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


@dataclass
class World:
    """Two synthetic organizations with distinct personas."""

    acme: uuid.UUID
    globex: uuid.UUID
    api: ApiClient

    def acme_as(self, persona: str):
        return self.api.as_(f"{persona}@acme.test", self.acme)

    def globex_as(self, persona: str):
        return self.api.as_(f"{persona}@globex.test", self.globex)


@pytest.fixture
def app(db: Database, tmp_path: Path):
    return create_app(Settings(env="test", object_store_path=tmp_path / "objects"), db=db)


@pytest.fixture
def world(db: Database, two_orgs, app) -> World:
    acme, globex = two_orgs
    for org, domain in ((acme, "acme.test"), (globex, "globex.test")):
        add_member(db, org, f"admin@{domain}", ["org_admin"])
        add_member(db, org, f"operator@{domain}", ["finance_operator"])
        add_member(db, org, f"approver@{domain}", ["finance_approver"], limit_minor=10_000_000_00)
        add_member(db, org, f"approver2@{domain}", ["finance_approver"], limit_minor=50_000_00)
        add_member(db, org, f"auditor@{domain}", ["auditor"])
        add_member(db, org, f"author@{domain}", ["policy_author"])
        add_member(db, org, f"publisher@{domain}", ["policy_publisher"])
    return World(acme=acme, globex=globex, api=ApiClient(TestClient(app)))


@pytest.fixture
def acme_operator(db: Database, world: World):
    return actor_for(db, "operator@acme.test", world.acme)


@pytest.fixture
def runtime(app):
    return app.state.runtime
