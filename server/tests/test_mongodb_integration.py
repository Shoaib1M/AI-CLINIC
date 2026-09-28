"""Runs the core flow against a real MongoDB server (e.g. your Atlas cluster).

Skipped unless TEST_MONGODB_URI is set:

    TEST_MONGODB_URI="mongodb+srv://USER:PASS@cluster0.example.mongodb.net/" pytest tests/test_mongodb_integration.py

It uses a throwaway database named ai_clinic_test_<random> and drops it afterwards.
"""

import os
import uuid

import pytest

from app import create_app

from .conftest import add_user, future

URI = os.getenv("TEST_MONGODB_URI")
pytestmark = pytest.mark.skipif(not URI, reason="set TEST_MONGODB_URI to run against a real MongoDB")


@pytest.fixture
def real_app():
    db_name = f"ai_clinic_test_{uuid.uuid4().hex[:8]}"
    overrides = {"MONGODB_URI": URI, "MONGODB_DB": db_name}
    app = create_app("testing", overrides)
    yield app, overrides
    app.extensions["mongo_client"].drop_database(db_name)


def test_full_flow_and_persistence_on_real_mongodb(real_app):
    app, overrides = real_app
    add_user(app, "frontdesk1", "Sarah Johnson", "frontdesk", "desk-pass-123")
    add_user(app, "doctor1", "Dr. Evelyn Reed", "doctor", "doctor-pass-123")
    client = app.test_client()

    assert client.get("/api/health").json["data"]["database"] == "ok"

    def login(user, pw):
        token = client.post("/api/auth/login", json={"username": user, "password": pw}).json["data"]["token"]
        return {"Authorization": f"Bearer {token}"}

    desk, doc = login("frontdesk1", "desk-pass-123"), login("doctor1", "doctor-pass-123")
    created = client.post(
        "/api/appointments",
        json={
            "patient": {"full_name": "Asha Verma", "phone": "+91 98765 43210"},
            "scheduled_at": future(),
            "appointment_type": "consultation",
            "symptoms": ["cough", "runny nose", "sneezing", "sore throat", "congestion"],
        },
        headers=desk,
    )
    assert created.status_code == 201
    appointment = created.json["data"]
    assert appointment["prediction"]["predicted_disease"] == "Common Cold"

    # Unique index: the same person is reused, not duplicated.
    again = client.post(
        "/api/appointments",
        json={"patient": {"full_name": "asha verma", "phone": "+91 98765 43210"}, "scheduled_at": future(2),
              "appointment_type": "follow_up", "symptoms": ["cough"]},
        headers=desk,
    ).json["data"]
    assert again["patient"]["id"] == appointment["patient"]["id"]

    listed = client.get("/api/appointments?q=asha&sort=confidence&order=desc", headers=doc).json
    assert listed["meta"]["total"] == 2
    assert client.get("/api/appointments/stats", headers=doc).json["data"]["total_patients"] == 1

    rx = client.post(
        "/api/prescriptions",
        json={"appointment_id": appointment["id"], "diagnosis": "Common cold", "medications": [{"name": "Rest"}]},
        headers=doc,
    ).json["data"]
    pdf = client.get(f"/api/prescriptions/{rx['id']}/pdf", headers=doc)
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    assert client.patch(f"/api/appointments/{appointment['id']}", json={"status": "completed"}, headers=doc).status_code == 200

    # A new app instance (a "restart") sees the same data.
    restarted = create_app("testing", {**overrides, "JWT_SECRET": app.config["JWT_SECRET"]}).test_client()
    detail = restarted.get(f"/api/appointments/{appointment['id']}", headers=doc).json["data"]
    assert detail["status"] == "completed"
    assert detail["prescriptions"][0]["id"] == rx["id"]
    assert [v["id"] for v in detail["visit_history"]] == [again["id"]]
