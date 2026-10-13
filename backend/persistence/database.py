"""Engine, transactions and tenant-scoped sessions.

``Database.tenant()`` opens one short transaction bound to a verified
organization. On PostgreSQL it sets ``app.organization_id`` (and the identity
subject) with ``set_config(..., true)`` so row-level security applies and the
setting disappears at commit, which keeps pooled connections clean.

On SQLite (local development and quick tests) writes use ``BEGIN IMMEDIATE`` so
concurrent transactions serialise instead of interleaving; tenant scoping is
enforced by ``TenantSession`` helpers only.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TypeVar

from sqlalchemy import Engine, Select, create_engine, event, select, text
from sqlalchemy.orm import Session, sessionmaker

from backend.errors import NotFound
from backend.persistence.base import is_tenant_owned

T = TypeVar("T")


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn: Any, _: Any) -> None:
        dbapi_conn.isolation_level = None  # let us emit BEGIN ourselves
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Any) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")


def make_engine(url: str, **kwargs: Any) -> Engine:
    if url.startswith("sqlite"):
        path = url.split("///", 1)[-1]
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(url, connect_args={"check_same_thread": False}, **kwargs)
        _configure_sqlite(engine)
        return engine
    kwargs.setdefault("pool_size", 10)
    kwargs.setdefault("max_overflow", 5)
    kwargs.setdefault("pool_pre_ping", True)
    return create_engine(url, **kwargs)


class TenantSession:
    """A session whose reads and writes are confined to one organization."""

    def __init__(self, session: Session, organization_id: uuid.UUID, actor: Any = None):
        self.session = session
        self.organization_id = organization_id
        self.actor = actor

    # -- reads ---------------------------------------------------------------

    def select(self, model: type[T]) -> Select[tuple[T]]:
        stmt = select(model)
        if is_tenant_owned(model):
            stmt = stmt.where(model.organization_id == self.organization_id)  # type: ignore[attr-defined]
        return stmt

    def get(self, model: type[T], object_id: uuid.UUID, *, for_update: bool = False) -> T:
        """Fetch by id within the tenant. Missing and cross-tenant both raise 404."""
        found = self.find(model, object_id, for_update=for_update)
        if found is None:
            raise NotFound(f"{model.__name__} not found", code="NOT_FOUND")
        return found

    def find(self, model: type[T], object_id: uuid.UUID, *, for_update: bool = False) -> T | None:
        stmt = self.select(model).where(model.id == object_id)  # type: ignore[attr-defined]
        if for_update:
            stmt = stmt.with_for_update()
        return self.session.scalars(stmt).first()

    def scalars(self, stmt: Select[tuple[T]]) -> Sequence[T]:
        return self.session.scalars(stmt).all()

    def first(self, stmt: Select[tuple[T]]) -> T | None:
        return self.session.scalars(stmt).first()

    # -- writes --------------------------------------------------------------

    def add(self, obj: T) -> T:
        if is_tenant_owned(type(obj)):
            current = getattr(obj, "organization_id", None)
            if current is None:
                obj.organization_id = self.organization_id  # type: ignore[attr-defined]
            elif current != self.organization_id:
                raise NotFound("Referenced object not found", code="NOT_FOUND")
        self.session.add(obj)
        return obj

    def flush(self) -> None:
        self.session.flush()


class Database:
    def __init__(self, url: str, *, admin_url: str | None = None, **engine_kwargs: Any):
        self.url = url
        self.engine = make_engine(url, **engine_kwargs)
        self.is_postgres = self.engine.dialect.name == "postgresql"
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.admin_url = admin_url or url
        self._admin_engine: Engine | None = None

    @property
    def admin_engine(self) -> Engine:
        """Owner connection for migrations, seeding and test resets only."""
        if self._admin_engine is None:
            self._admin_engine = (
                self.engine if self.admin_url == self.url else make_engine(self.admin_url)
            )
        return self._admin_engine

    def _set_context(
        self, session: Session, organization_id: uuid.UUID | None, subject: str | None
    ) -> None:
        if not self.is_postgres:
            return
        session.execute(
            text(
                "SELECT set_config('app.organization_id', :org, true),"
                " set_config('app.identity_subject', :sub, true)"
            ),
            {"org": str(organization_id) if organization_id else "", "sub": subject or ""},
        )

    @contextmanager
    def tenant(
        self, organization_id: uuid.UUID, *, subject: str | None = None, actor: Any = None
    ) -> Iterator[TenantSession]:
        with self._sessions() as session, session.begin():
            self._set_context(session, organization_id, subject)
            yield TenantSession(session, organization_id, actor)

    @contextmanager
    def identity(self, subject: str) -> Iterator[Session]:
        """Cross-organization lookups permitted for one identity (its memberships)."""
        with self._sessions() as session, session.begin():
            self._set_context(session, None, subject)
            yield session

    @contextmanager
    def system(self) -> Iterator[Session]:
        """Untenanted metadata (jobs/outbox dispatch). Never used for tenant payloads."""
        with self._sessions() as session, session.begin():
            self._set_context(session, None, None)
            yield session

    @contextmanager
    def admin(self) -> Iterator[Session]:
        with Session(self.admin_engine, expire_on_commit=False) as session, session.begin():
            yield session

    def dispose(self) -> None:
        self.engine.dispose()
        if self._admin_engine is not None and self._admin_engine is not self.engine:
            self._admin_engine.dispose()
