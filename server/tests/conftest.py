import os
import uuid
from datetime import datetime, timedelta

import pytest

from app import create_app
from app.cli import _create_user

PASSWORDS = {"doctor1": "doctor-pass-123", "frontdesk1": "desk-pass-123"}


def future(days: int = 1, hour: int = 10) -> str:
    return (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=30).strftime("%Y-%m-%dT%H:%M")


def add_user(app, username, full_name, role, password):
    with app.app_context():
        return _create_user(username, full_name, role, password)


@pytest.fixture
def app():
    # By default TestingConfig uses mongomock: each app gets its own empty
    # in-memory database. With TEST_MONGODB_URI set, every test instead runs
    # against a throwaway database on that real server, dropped afterwards.
    real_uri = os.getenv("TEST_MONGODB_URI")
    overrides = {"MONGODB_URI": real_uri, "MONGODB_DB": f"ai_clinic_test_{uuid.uuid4().hex[:8]}"} if real_uri else None
    app = create_app("testing", overrides)
    add_user(app, "doctor1", "Dr. Evelyn Reed", "doctor", PASSWORDS["doctor1"])
    add_user(app, "frontdesk1", "Sarah Johnson", "frontdesk", PASSWORDS["frontdesk1"])
    yield app
    if real_uri:
        app.extensions["mongo_client"].drop_database(overrides["MONGODB_DB"])


@pytest.fixture
def client(app):
    return app.test_client()


def _headers(client, username):
    res = client.post("/api/auth/login", json={"username": username, "password": PASSWORDS[username]})
    assert res.status_code == 200, res.json
    return {"Authorization": f"Bearer {res.json['data']['token']}"}


@pytest.fixture
def doctor(client):
    return _headers(client, "doctor1")


@pytest.fixture
def frontdesk(client):
    return _headers(client, "frontdesk1")


@pytest.fixture
def make_appointment(client, frontdesk):
    def _make(name="Asha Verma", phone="+91 98765 43210", symptoms=None, **overrides):
        payload = {
            "patient": {"full_name": name, "phone": phone},
            "scheduled_at": future(),
            "appointment_type": "consultation",
            "symptoms": symptoms or ["cough", "runny nose", "sneezing", "sore throat", "congestion"],
            **overrides,
        }
        res = client.post("/api/appointments", json=payload, headers=frontdesk)
        assert res.status_code == 201, res.json
        return res.json["data"]

    return _make
