from __future__ import annotations


def test_register_returns_token(client):
    resp = client.post("/auth/register", json={"email": "a@test.com", "password": "secret123"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


def test_register_duplicate_email_conflicts(client):
    payload = {"email": "dup@test.com", "password": "secret123"}
    assert client.post("/auth/register", json=payload).status_code == 200
    resp = client.post("/auth/register", json=payload)
    assert resp.status_code == 409


def test_register_rejects_short_password(client):
    resp = client.post("/auth/register", json={"email": "short@test.com", "password": "123"})
    assert resp.status_code == 422


def test_login_success_and_failure(client):
    client.post("/auth/register", json={"email": "login@test.com", "password": "secret123"})
    ok = client.post("/auth/login", json={"email": "login@test.com", "password": "secret123"})
    assert ok.status_code == 200
    bad = client.post("/auth/login", json={"email": "login@test.com", "password": "wrongpass"})
    assert bad.status_code == 401


def test_me_requires_authentication(client):
    assert client.get("/auth/me").status_code == 401


def test_me_returns_current_user(client, auth):
    headers, email = auth()
    resp = client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == email
    assert body["learner_level"] == "beginner"


def test_learner_assessment_updates_profile(client, auth):
    headers, _ = auth()
    resp = client.post(
        "/auth/assessment",
        json={"learner_level": "intermediate", "learning_style": "theory"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["learner_level"] == "intermediate"
