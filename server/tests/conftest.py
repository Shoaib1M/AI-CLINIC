from datetime import datetime, timedelta

import pytest

from app import create_app
from app.extensions import db
from app.models import User

PASSWORDS = {"doctor1": "doctor-pass-123", "frontdesk1": "desk-pass-123"}


def future(days: int = 1, hour: int = 10) -> str:
    return (datetime.now() + timedelta(days=days)).replace(hour=hour, minute=30).strftime("%Y-%m-%dT%H:%M")


@pytest.fixture
def app():
    app = create_app("testing")
    with app.app_context():
        for username, name, role in (
            ("doctor1", "Dr. Evelyn Reed", "doctor"),
            ("frontdesk1", "Sarah Johnson", "frontdesk"),
        ):
            user = User(username=username, full_name=name, role=role)
            user.set_password(PASSWORDS[username])
            db.session.add(user)
        db.session.commit()
    yield app
    with app.app_context():
        db.drop_all()


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
