import hashlib

import pytest

from backend.adapters.object_store.grants import GrantSigner
from backend.errors import Forbidden
from backend.evidence.inspection import EICAR_MARKER

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def upload(client, data: bytes, *, media_type="application/pdf", declared=None, size=None):
    created = client.post(
        "/v1/uploads",
        json={
            "filename": "../../etc/invoice 42.pdf",
            "media_type": media_type,
            "size": size or len(data),
            "declared_sha256": declared or sha(data),
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    put = client.client.put(body["upload_url"], content=data)
    assert put.status_code == 204, put.text
    done = client.post(f"/v1/uploads/{body['document_version_id']}/complete")
    assert done.status_code == 202
    return body, done.json()


def test_clean_upload_is_verified_and_downloadable(world):
    operator = world.acme_as("operator")
    body, doc = upload(operator, PDF)
    assert doc["status"] == "CLEAN"
    assert doc["sha256"] == sha(PDF)
    assert doc["original_name"] == "invoice 42.pdf"  # path components stripped

    grant = operator.post(f"/v1/documents/{body['document_version_id']}/download-grants")
    assert grant.status_code == 201
    content = world.api.client.get(grant.json()["download_url"])
    assert content.status_code == 200
    assert content.content == PDF
    assert content.headers["x-content-type-options"] == "nosniff"


def test_hash_mismatch_is_rejected(world):
    _, doc = upload(world.acme_as("operator"), PDF, declared=sha(b"something else"))
    assert doc["status"] == "REJECTED"
    assert doc["rejection_reason"] == "HASH_MISMATCH"


def test_media_type_must_match_content(world):
    fake_pdf = b"MZ\x90\x00 not really a pdf"
    _, doc = upload(world.acme_as("operator"), fake_pdf)
    assert doc["rejection_reason"] == "MEDIA_TYPE_MISMATCH"


def test_malware_is_rejected_and_not_downloadable(world):
    operator = world.acme_as("operator")
    data = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + EICAR_MARKER + b"!$H+H*"
    body, doc = upload(operator, data, media_type="text/plain")
    assert doc["status"] == "REJECTED"
    assert doc["malware_status"] == "INFECTED"
    grant = operator.post(f"/v1/documents/{body['document_version_id']}/download-grants")
    assert grant.status_code == 409


def test_upload_larger_than_declared_is_refused(world):
    operator = world.acme_as("operator")
    created = operator.post(
        "/v1/uploads",
        json={
            "filename": "a.pdf",
            "media_type": "application/pdf",
            "size": 10,
            "declared_sha256": sha(PDF),
        },
    ).json()
    resp = world.api.client.put(created["upload_url"], content=PDF)
    assert resp.status_code == 422


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        ({"media_type": "application/x-msdownload"}, "MEDIA_TYPE"),
        ({"size": 50 * 1024 * 1024}, "FILE_SIZE"),
        ({"declared_sha256": "md5:abc"}, "HASH_FORMAT"),
    ],
)
def test_upload_policy_limits(world, payload, code):
    body = {
        "filename": "a.pdf",
        "media_type": "application/pdf",
        "size": 100,
        "declared_sha256": sha(b"x"),
        **payload,
    }
    resp = world.acme_as("operator").post("/v1/uploads", json=body)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == code


def test_other_tenant_cannot_read_or_complete_documents(world):
    body, _ = upload(world.acme_as("operator"), PDF)
    doc_id = body["document_version_id"]
    globex = world.globex_as("operator")
    assert globex.get(f"/v1/documents/{doc_id}").status_code == 404
    assert globex.post(f"/v1/documents/{doc_id}/download-grants").status_code == 404
    assert globex.post(f"/v1/uploads/{doc_id}/complete").status_code == 404


def test_new_version_of_a_document(world):
    operator = world.acme_as("operator")
    first, _ = upload(operator, PDF)
    data = PDF + b"%corrected\n"
    created = operator.post(
        "/v1/uploads",
        json={
            "filename": "invoice.pdf",
            "media_type": "application/pdf",
            "size": len(data),
            "declared_sha256": sha(data),
            "document_id": first["document_id"],
        },
    ).json()
    assert created["version"] == 2
    assert created["document_id"] == first["document_id"]


def test_auditor_cannot_upload(world):
    resp = world.acme_as("auditor").post(
        "/v1/uploads",
        json={"filename": "a", "media_type": "text/plain", "size": 1, "declared_sha256": sha(b"")},
    )
    assert resp.status_code == 403


def test_grants_are_signed_scoped_and_expire():
    import uuid

    signer = GrantSigner("secret", ttl_seconds=60)
    org, doc = uuid.uuid4(), uuid.uuid4()
    token, _ = signer.issue(org, f"{org}/documents/x", doc, "download", now=1000)
    assert signer.verify(token, "download", now=1010).organization_id == org
    with pytest.raises(Forbidden):
        signer.verify(token, "upload", now=1010)
    with pytest.raises(Forbidden):
        signer.verify(token, "download", now=1100)
    tampered = token[:-2] + ("AA" if not token.endswith("AA") else "BB")
    with pytest.raises(Forbidden):
        signer.verify(tampered, "download", now=1010)
    with pytest.raises(Forbidden):
        GrantSigner("other", 60).verify(token, "download", now=1010)
