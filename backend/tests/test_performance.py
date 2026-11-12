from __future__ import annotations

from app.services.performance import _adapt_difficulty, _normalize


def test_normalize_matches_equivalent_answers():
    assert _normalize("  Atomicity,  Consistency. ") == _normalize("atomicity consistency")


def test_normalize_distinguishes_different_answers():
    assert _normalize("index") != _normalize("view")


def test_normalize_handles_empty():
    assert _normalize(None) == ""
    assert _normalize("   ") == ""


def test_adapt_difficulty_climbs_on_high_score():
    assert _adapt_difficulty("beginner", 0.9) == "intermediate"


def test_adapt_difficulty_drops_on_low_score():
    assert _adapt_difficulty("exam", 0.2) == "intermediate"


def test_adapt_difficulty_holds_mid_range():
    assert _adapt_difficulty("beginner", 0.6) == "beginner"
    assert _adapt_difficulty("exam", 0.9) == "exam"


def test_performance_empty_for_new_user(client, auth):
    headers, _ = auth()
    resp = client.get("/performance", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["quizzes_taken"] == 0
    assert body["history"] == []
    assert body["topics"] == []
    assert body["weak_topics"] == []
