from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from app.core import ratelimit


def test_ask_requires_auth(client, upload_doc):
    _, doc = upload_doc()
    resp = client.post("/ask", json={"document_id": doc["id"], "question": "What is ACID?"})
    assert resp.status_code == 401


def test_ask_unknown_document_returns_404(client, auth, mock_ai):
    headers, _ = auth()
    resp = client.post(
        "/ask", json={"document_id": 999999, "question": "What is ACID?"}, headers=headers
    )
    assert resp.status_code == 404


def test_ask_rejects_empty_question(client, upload_doc):
    headers, doc = upload_doc()
    resp = client.post("/ask", json={"document_id": doc["id"], "question": ""}, headers=headers)
    assert resp.status_code == 422


def test_ask_rejects_overlong_question(client, upload_doc):
    headers, doc = upload_doc()
    resp = client.post(
        "/ask", json={"document_id": doc["id"], "question": "x" * 2001}, headers=headers
    )
    assert resp.status_code == 422


def test_ask_returns_answer_and_sources(client, upload_doc):
    headers, doc = upload_doc()
    resp = client.post(
        "/ask", json={"document_id": doc["id"], "question": "What is normalization?"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"]
    assert body["sources"] == ["chunk-1", "chunk-2"]


def test_ask_is_rate_limited(client, upload_doc):
    headers, doc = upload_doc()
    uid = client.get("/auth/me", headers=headers).json()["id"]
    # Pre-fill the sliding window so the very next call exceeds the limit.
    ratelimit._HITS[f"ask:{uid}"].extend([time.monotonic()] * 30)
    resp = client.post(
        "/ask", json={"document_id": doc["id"], "question": "What is ACID?"}, headers=headers
    )
    assert resp.status_code == 429


def test_ratelimit_check_unit():
    ratelimit.reset()
    for _ in range(3):
        ratelimit.check("unit:1", limit=3)
    with pytest.raises(HTTPException) as exc:
        ratelimit.check("unit:1", limit=3)
    assert exc.value.status_code == 429
