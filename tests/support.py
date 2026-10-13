"""Helpers shared by test modules."""

from __future__ import annotations

import os

import pytest

BACKEND = os.environ.get("FINGUARD_TEST_BACKEND", "postgres")

pg_only = pytest.mark.skipif(BACKEND == "sqlite", reason="row-level security requires PostgreSQL")


def add_member(db, organization_id, subject, roles, *, limit_minor=None):
    from backend.identity.models import Membership

    with db.admin() as session:
        member = Membership(
            organization_id=organization_id,
            identity_subject=subject,
            display_name=subject.split("@")[0].title(),
            roles=list(roles),
            approval_limit_minor=limit_minor,
        )
        session.add(member)
        session.flush()
        return member.id


class ApiClient:
    """Thin wrapper over TestClient that sends dev-stub identity headers."""

    def __init__(self, client):
        self.client = client

    def as_(self, subject, organization_id=None):
        headers = {"X-Dev-User": subject}
        if organization_id is not None:
            headers["X-Organization-Id"] = str(organization_id)
        return _Bound(self.client, headers)


class _Bound:
    def __init__(self, client, headers):
        self.client = client
        self.headers = headers

    def _call(self, method, url, **kwargs):
        headers = {**self.headers, **kwargs.pop("headers", {})}
        return self.client.request(method, url, headers=headers, **kwargs)

    def get(self, url, **kw):
        return self._call("GET", url, **kw)

    def post(self, url, **kw):
        return self._call("POST", url, **kw)

    def patch(self, url, **kw):
        return self._call("PATCH", url, **kw)


def actor_for(db, subject, organization_id):
    from backend.identity.service import resolve_user

    return resolve_user(db, subject, organization_id)
