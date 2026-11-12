"""Shared pytest fixtures.

The environment (database, chroma dir, upload dir, JWT secret) is redirected to
throwaway temp paths *before* the app is imported, so tests never touch the real
development database and the LLM/vector store are mocked for speed and
determinism.
"""
from __future__ import annotations

import json
import os
import pathlib
import tempfile
from uuid import uuid4

# ---------------------------------------------------------------------------
# Isolated environment — must run before any `app.*` import.
# ---------------------------------------------------------------------------
_TMP = pathlib.Path(tempfile.mkdtemp(prefix="studysync_tests_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["CHROMA_DIR"] = str(_TMP / "chroma")
os.environ["UPLOAD_DIR"] = str(_TMP / "uploads")
os.environ["JWT_SECRET"] = "test-secret-key-for-pytest-only"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.session import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Document, Quiz  # noqa: E402

# Fail fast if the isolation above did not take effect.
assert "studysync_tests_" in settings.database_url, settings.database_url


SAMPLE_TEXT = (
    "Database Management Systems notes.\n"
    "ACID stands for Atomicity, Consistency, Isolation, Durability.\n"
    "Normalization reduces redundancy. 2NF removes partial dependencies.\n"
    "Indexing speeds up data retrieval using B-trees.\n"
).encode()

FAKE_SUMMARY = {
    "key_concepts": ["ACID", "Normalization", "Indexing"],
    "definitions": [
        {"term": "ACID", "definition": "Atomicity, Consistency, Isolation, Durability"}
    ],
    "important_points": ["Normalization reduces redundancy"],
    "examples": [{"concept": "ACID", "example": "A bank transfer is atomic"}],
    "exam_notes": "### Rapid Exam Revision Notes\n- ACID guarantees reliable transactions.",
}

FAKE_QUIZ = {
    "questions": [
        {
            "type": "mcq",
            "prompt": "What does ACID stand for?",
            "options": ["Atomicity Consistency Isolation Durability", "Apples", "Oranges", "Grapes"],
            "answer": "Atomicity Consistency Isolation Durability",
            "topic": "ACID",
            "explanation": "Standard ACID definition.",
        },
        {
            "type": "mcq",
            "prompt": "Which normal form removes partial dependencies?",
            "options": ["1NF", "2NF", "3NF", "BCNF"],
            "answer": "2NF",
            "topic": "Normalization",
            "explanation": "2NF removes partial dependencies.",
        },
        {
            "type": "mcq",
            "prompt": "What speeds up data retrieval?",
            "options": ["Index", "View", "Trigger", "Cursor"],
            "answer": "Index",
            "topic": "Indexing",
            "explanation": "Indexes speed up retrieval.",
        },
        {
            "type": "true_false",
            "prompt": "Durability means committed data survives crashes.",
            "options": ["True", "False"],
            "answer": "True",
            "topic": "ACID",
            "explanation": "Durability persists committed data.",
        },
        {
            "type": "short",
            "prompt": "What does normalization reduce?",
            "options": None,
            "answer": "redundancy",
            "topic": "Normalization",
            "explanation": "It reduces redundancy.",
        },
    ]
}

FAKE_DOUBT_ANSWER = (
    "### \U0001f4a1 Explanation\nNormalization organizes data to reduce redundancy.\n"
    "### \U0001f50d Intuitive Analogy\nLike sorting a messy drawer.\n"
    "### \U0001f4cc Concrete Example\nSplitting one big table into related tables.\n"
    "### \U0001f4dd Step-by-Step Breakdown\n1. Identify dependencies.\n"
    "### \U0001f3af Exam Revision Tip\nRemember 1NF, 2NF, 3NF order."
)


@pytest.fixture
def client():
    """TestClient bound to a freshly reset database and rate-limit state."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ratelimit.reset()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth(client):
    """Factory returning (Authorization headers, email) for a fresh user."""

    def _make(email: str | None = None):
        email = email or f"user_{uuid4().hex[:10]}@test.com"
        resp = client.post("/auth/register", json={"email": email, "password": "secret123"})
        assert resp.status_code == 200, resp.text
        token = resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}, email

    return _make


@pytest.fixture
def mock_ai(monkeypatch):
    """Replace every LLM + vector-store call with fast deterministic fakes."""

    def fake_complete_json(system: str, user: str, num_predict: int | None = None) -> str:
        if "Summarization Agent" in system:
            return json.dumps(FAKE_SUMMARY)
        if "Quiz Generation Agent" in system:
            return json.dumps(FAKE_QUIZ)
        return "{}"

    def fake_complete(system: str, user: str, num_predict: int | None = None) -> str:
        if "grade short answers" in system.lower():
            return "YES"
        return FAKE_DOUBT_ANSWER

    monkeypatch.setattr("app.agents.summarizer.complete_json", fake_complete_json)
    monkeypatch.setattr("app.agents.quiz.complete_json", fake_complete_json)
    monkeypatch.setattr("app.agents.doubt.complete", fake_complete)
    monkeypatch.setattr("app.graphs.learning_graph.complete", fake_complete)
    monkeypatch.setattr("app.services.performance.complete", fake_complete)

    # Vector store + retrieval (no embeddings / ChromaDB needed in tests).
    monkeypatch.setattr(
        "app.routers.documents.index_document",
        lambda user_id, document_id, text: max(1, len(text) // 900),
    )
    monkeypatch.setattr(
        "app.routers.documents.delete_document_index", lambda user_id, document_id: None
    )
    monkeypatch.setattr(
        "app.graphs.learning_graph.retrieve_context",
        lambda user_id, document_id, query, k=6: (
            "MOCK CONTEXT about ACID, normalization and indexing.",
            ["chunk-1", "chunk-2"],
        ),
    )
    return monkeypatch


@pytest.fixture
def upload_doc(client, auth, mock_ai):
    """Factory that uploads a text document and returns (headers, document_json)."""

    def _upload(content: bytes = SAMPLE_TEXT, filename: str = "notes.txt"):
        headers, _ = auth()
        resp = client.post(
            "/documents/upload",
            files={"file": (filename, content, "text/plain")},
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        return headers, resp.json()

    return _upload


@pytest.fixture
def seed_quiz(client, auth):
    """Seed a ready (or custom-status) quiz row directly for grading tests."""

    def _seed(questions, difficulty: str = "beginner", status: str = "ready"):
        headers, _ = auth()
        me = client.get("/auth/me", headers=headers).json()
        user_id = me["id"]
        db = SessionLocal()
        try:
            doc = Document(
                user_id=user_id,
                filename="seed.txt",
                filepath=str(_TMP / "seed.txt"),
                status="ready",
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            quiz = Quiz(
                user_id=user_id,
                document_id=doc.id,
                difficulty=difficulty,
                status=status,
                questions=questions,
            )
            db.add(quiz)
            db.commit()
            db.refresh(quiz)
            return headers, quiz.id, doc.id
        finally:
            db.close()

    return _seed
