from datetime import datetime, timedelta, timezone

import jwt

from app.extensions import mongo


def test_login_returns_token_and_user(client):
    res = client.post("/api/auth/login", json={"username": "doctor1", "password": "doctor-pass-123"})
    assert res.status_code == 200
    data = res.json["data"]
    assert data["token"]
    assert data["user"] == {"id": 1, "username": "doctor1", "full_name": "Dr. Evelyn Reed", "role": "doctor"}
    assert "password" not in str(data)


def test_login_wrong_password_and_unknown_user_look_identical(client):
    wrong = client.post("/api/auth/login", json={"username": "doctor1", "password": "nope-nope"})
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json == unknown.json


def test_login_requires_fields(client):
    res = client.post("/api/auth/login", json={"username": ""})
    assert res.status_code == 400
    assert set(res.json["error"]["details"]) == {"username", "password"}


def test_login_rejects_non_json(client):
    res = client.post("/api/auth/login", data="username=doctor1", content_type="text/plain")
    assert res.status_code == 400
    assert res.json["error"]["code"] == "INVALID_JSON"


def test_me_requires_valid_token(client, doctor):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401
    res = client.get("/api/auth/me", headers=doctor)
    assert res.status_code == 200 and res.json["data"]["role"] == "doctor"


def test_expired_token_rejected(app, client):
    past = datetime.now(timezone.utc) - timedelta(hours=10)
    token = jwt.encode(
        {"sub": "1", "role": "doctor", "iat": past, "exp": past + timedelta(hours=1)},
        app.config["JWT_SECRET"],
        algorithm="HS256",
    )
    res = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert res.json["error"]["code"] == "TOKEN_EXPIRED"


def test_token_signed_with_other_secret_rejected(client):
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "1", "iat": now, "exp": now + timedelta(hours=1)}, "x" * 40, algorithm="HS256")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unsigned_token_rejected(client):
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": "1", "iat": now, "exp": now + timedelta(hours=1)}, None, algorithm="none")
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_deactivated_user_loses_access_immediately(app, client, doctor):
    with app.app_context():
        mongo.db.users.update_one({"username": "doctor1"}, {"$set": {"is_active": False}})
    assert client.get("/api/auth/me", headers=doctor).status_code == 401


def test_role_enforced(client, doctor, frontdesk):
    # Only the front desk books appointments; only doctors write prescriptions.
    assert client.post("/api/appointments", json={}, headers=doctor).status_code == 403
    assert client.post("/api/prescriptions", json={}, headers=frontdesk).status_code == 403


def test_protected_endpoints_require_auth(client):
    for method, path in [
        ("get", "/api/appointments"),
        ("post", "/api/appointments"),
        ("get", "/api/appointments/1"),
        ("patch", "/api/appointments/1"),
        ("get", "/api/appointments/stats"),
        ("get", "/api/patients?q=as"),
        ("post", "/api/predictions"),
        ("post", "/api/prescriptions"),
        ("get", "/api/prescriptions/1/pdf"),
    ]:
        assert getattr(client, method)(path).status_code == 401, path
