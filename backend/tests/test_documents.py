from __future__ import annotations

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import Attempt, Document, Performance, Quiz, TopicScore


def test_upload_requires_auth(client):
    resp = client.post("/documents/upload", files={"file": ("n.txt", b"hi", "text/plain")})
    assert resp.status_code == 401


def test_upload_rejects_unsupported_format(client, auth):
    headers, _ = auth()
    resp = client.post(
        "/documents/upload",
        files={"file": ("bad.exe", b"binary", "application/octet-stream")},
        headers=headers,
    )
    assert resp.status_code == 400


def test_upload_text_document_succeeds(upload_doc):
    _, doc = upload_doc()
    assert doc["status"] == "ready"
    assert doc["chunks_stored"] >= 1
    assert doc["id"] > 0


def test_upload_enforces_size_limit(client, auth, mock_ai, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    headers, _ = auth()
    big = b"x" * (int(1.2 * 1024 * 1024))
    resp = client.post(
        "/documents/upload",
        files={"file": ("big.txt", big, "text/plain")},
        headers=headers,
    )
    assert resp.status_code == 413


def test_summary_becomes_ready_with_concepts(client, upload_doc):
    headers, doc = upload_doc()
    resp = client.get(f"/documents/{doc['id']}/summary", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["key_concepts"]
    assert body["error"] is None


def test_documents_are_scoped_to_owner(client, upload_doc, auth):
    _, doc = upload_doc()
    other_headers, _ = auth()
    listing = client.get("/documents", headers=other_headers).json()
    assert doc["id"] not in [d["id"] for d in listing]


def test_delete_document_cascades_related_rows(client, upload_doc):
    headers, doc = upload_doc()
    did = doc["id"]

    quiz = client.post("/quiz", json={"document_id": did}, headers=headers).json()
    quiz_id = quiz["id"]
    detail = client.get(f"/quiz/{quiz_id}", headers=headers).json()
    assert detail["status"] == "ready"
    # Submit so Attempt / TopicScore / Performance rows exist.
    answers = ["Atomicity Consistency Isolation Durability", "2NF", "Index", "True", "redundancy"]
    submit = client.post(f"/quiz/{quiz_id}/submit", json={"answers": answers}, headers=headers)
    assert submit.status_code == 200

    assert client.delete(f"/documents/{did}", headers=headers).status_code == 200

    db = SessionLocal()
    try:
        assert db.query(Document).filter(Document.id == did).count() == 0
        assert db.query(Quiz).filter(Quiz.document_id == did).count() == 0
        assert db.query(TopicScore).filter(TopicScore.document_id == did).count() == 0
        assert db.query(Performance).filter(Performance.document_id == did).count() == 0
    finally:
        db.close()


def test_delete_unknown_document_returns_404(client, auth):
    headers, _ = auth()
    assert client.delete("/documents/999999", headers=headers).status_code == 404
