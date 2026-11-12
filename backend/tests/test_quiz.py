from __future__ import annotations

from tests.conftest import FAKE_QUIZ


def test_create_quiz_requires_auth(client, upload_doc):
    _, doc = upload_doc()
    assert client.post("/quiz", json={"document_id": doc["id"]}).status_code == 401


def test_create_quiz_unknown_document_returns_404(client, auth, mock_ai):
    headers, _ = auth()
    resp = client.post("/quiz", json={"document_id": 999999}, headers=headers)
    assert resp.status_code == 404


def test_quiz_generation_is_async_then_ready(client, upload_doc):
    headers, doc = upload_doc()
    created = client.post("/quiz", json={"document_id": doc["id"]}, headers=headers)
    assert created.status_code == 200
    body = created.json()
    # The POST returns immediately while the background task runs.
    assert body["status"] == "generating"
    assert body["questions"] == []

    detail = client.get(f"/quiz/{body['id']}", headers=headers).json()
    assert detail["status"] == "ready"
    assert len(detail["questions"]) == 5
    # Every generated question is normalized to a multiple-choice question.
    assert {q["type"] for q in detail["questions"]} == {"mcq"}
    assert all(len(q["options"]) >= 2 for q in detail["questions"])


def test_get_unknown_quiz_returns_404(client, auth):
    headers, _ = auth()
    assert client.get("/quiz/999999", headers=headers).status_code == 404


def test_submit_not_ready_quiz_returns_409(client, seed_quiz):
    headers, qid, _ = seed_quiz(FAKE_QUIZ["questions"], status="generating")
    resp = client.post(f"/quiz/{qid}/submit", json={"answers": ["x"] * 5}, headers=headers)
    assert resp.status_code == 409


def test_submit_grades_and_updates_performance(client, seed_quiz):
    headers, qid, did = seed_quiz(FAKE_QUIZ["questions"])
    # Deliberately messy casing/punctuation/whitespace to exercise normalization.
    answers = [
        "  atomicity consistency isolation durability. ",
        "2nf",
        "INDEX",
        "true",
        "redundancy",
    ]
    resp = client.post(f"/quiz/{qid}/submit", json={"answers": answers}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["score"] == 1.0
    assert all(item["correct"] for item in body["results"])

    perf = client.get(f"/performance?document_id={did}", headers=headers).json()
    assert perf["quizzes_taken"] == 1
    assert perf["latest_score"] == 1.0
    assert perf["best_score"] == 1.0
    assert perf["difficulty"] == "intermediate"  # 100% bumps difficulty up
    assert {t["topic"] for t in perf["topics"]} >= {"ACID", "Normalization", "Indexing"}


def test_submit_with_wrong_answers_scores_zero(client, seed_quiz):
    headers, qid, _ = seed_quiz(FAKE_QUIZ["questions"][:3])
    resp = client.post(
        f"/quiz/{qid}/submit", json={"answers": ["nope", "nope", "nope"]}, headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["score"] == 0.0
