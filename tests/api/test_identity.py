import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from backend.adapters.oidc.verifier import OidcVerifier
from backend.errors import Unauthenticated
from tests.support import add_member


def test_unauthenticated_requests_are_rejected(world):
    resp = world.api.client.get("/v1/session")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHENTICATED"


def test_session_resolves_membership_and_capabilities(world):
    resp = world.acme_as("operator").get("/v1/session")
    assert resp.status_code == 200
    body = resp.json()
    assert body["organization_id"] == str(world.acme)
    assert "proposal.create" in body["capabilities"]
    assert "approval.decide" not in body["capabilities"]


def test_non_member_cannot_select_another_organization(world):
    resp = world.api.as_("operator@acme.test", world.globex).get("/v1/session")
    assert resp.status_code == 404


def test_identity_with_two_memberships_must_choose(world, db):
    add_member(db, world.globex, "operator@acme.test", ["auditor"])
    resp = world.api.as_("operator@acme.test").get("/v1/session")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "ORGANIZATION_REQUIRED"
    me = world.api.as_("operator@acme.test").get("/v1/me").json()
    assert {m["organization_name"] for m in me["memberships"]} == {
        "Acme Distributors",
        "Globex Wholesale",
    }


def test_admin_manages_members_but_holds_no_financial_capability(world):
    admin = world.acme_as("admin")
    caps = admin.get("/v1/session").json()["capabilities"]
    assert "approval.decide" not in caps and "case.read" not in caps
    created = admin.post(
        "/v1/members",
        json={"subject": "new@acme.test", "display_name": "New", "roles": ["finance_operator"]},
    )
    assert created.status_code == 201
    listed = admin.get("/v1/members").json()
    assert "new@acme.test" in {m["identity_subject"] for m in listed}
    assert all(m["identity_subject"].endswith("@acme.test") for m in listed)


def test_admin_cannot_grant_themselves_approval(world):
    admin = world.acme_as("admin")
    me = next(
        m for m in admin.get("/v1/members").json() if m["identity_subject"] == "admin@acme.test"
    )
    resp = admin.patch(
        f"/v1/members/{me['id']}",
        json={"roles": ["org_admin", "finance_approver"], "reason": "self grant"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "SELF_ROLE_CHANGE"


def test_revocation_takes_effect_on_the_next_request(world):
    operator = world.acme_as("operator")
    assert operator.get("/v1/session").status_code == 200
    admin = world.acme_as("admin")
    member = next(
        m for m in admin.get("/v1/members").json() if m["identity_subject"] == "operator@acme.test"
    )
    resp = admin.patch(
        f"/v1/members/{member['id']}", json={"status": "REVOKED", "reason": "left company"}
    )
    assert resp.json()["authorization_revision"] == member["authorization_revision"] + 1
    assert operator.get("/v1/session").status_code == 404


def test_operator_cannot_manage_members(world):
    resp = world.acme_as("operator").get("/v1/members")
    assert resp.status_code == 403
    assert resp.json()["error"]["details"] == {"capability": "member.manage"}


def test_cross_tenant_member_update_is_not_found(world):
    globex_member = next(
        m
        for m in world.globex_as("admin").get("/v1/members").json()
        if m["identity_subject"] == "operator@globex.test"
    )
    resp = world.acme_as("admin").patch(
        f"/v1/members/{globex_member['id']}", json={"status": "REVOKED", "reason": "probe"}
    )
    assert resp.status_code == 404


def test_service_account_scopes_and_binding(world):
    admin = world.acme_as("admin")
    rejected = admin.post(
        "/v1/service-accounts", json={"name": "agent", "scopes": ["approval.decide"]}
    )
    assert rejected.status_code == 422
    created = admin.post(
        "/v1/service-accounts", json={"name": "agent", "scopes": ["proposal.create", "case.read"]}
    ).json()
    headers = {"Authorization": f"Bearer {created['token']}"}
    session = world.api.client.get("/v1/session", headers=headers).json()
    assert session["actor_type"] == "service"
    assert session["organization_id"] == str(world.acme)
    assert set(session["capabilities"]) == {"proposal.create", "case.read"}
    wrong_org = world.api.client.get(
        "/v1/session", headers={**headers, "X-Organization-Id": str(world.globex)}
    )
    assert wrong_org.status_code == 401
    bad = world.api.client.get("/v1/session", headers={"Authorization": "Bearer fgsa_nope"})
    assert bad.status_code == 401


def test_oidc_verifier_checks_signature_issuer_audience_and_expiry():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OidcVerifier(
        "https://idp.test", "finguard", key_resolver=lambda _token: key.public_key()
    )
    now = int(time.time())
    claims = {"sub": "u-1", "iss": "https://idp.test", "aud": "finguard", "iat": now}

    good = jwt.encode({**claims, "exp": now + 300}, key, algorithm="RS256")
    assert verifier.verify(good) == "u-1"

    for bad_claims in (
        {**claims, "exp": now - 3600},
        {**claims, "exp": now + 300, "aud": "other"},
        {**claims, "exp": now + 300, "iss": "https://evil.test"},
    ):
        with pytest.raises(Unauthenticated):
            verifier.verify(jwt.encode(bad_claims, key, algorithm="RS256"))

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode({**claims, "exp": now + 300}, other_key, algorithm="RS256")
    with pytest.raises(Unauthenticated):
        verifier.verify(forged)
