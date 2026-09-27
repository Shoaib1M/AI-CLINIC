from app import create_app
from app.extensions import db
from app.models import User

from .conftest import future


def test_predict_known_symptoms(client, doctor):
    res = client.post("/api/predictions", json={"symptoms": ["vomiting", "chills", "nausea", "body ache", "fever"]}, headers=doctor)
    assert res.status_code == 200
    data = res.json["data"]
    assert data["prediction"] == "Malaria"
    assert data["confidence_level"] in {"low", "moderate", "high"}
    assert len(data["top_predictions"]) == 3
    probabilities = [p["probability"] for p in data["top_predictions"]]
    assert probabilities == sorted(probabilities, reverse=True)
    assert data["top_predictions"][0]["probability"] == data["confidence"]
    assert "not a diagnosis" in data["disclaimer"]


def test_predict_top_k_and_warnings(client, doctor):
    data = client.post("/api/predictions", json={"symptoms": ["fever", "unicorn"], "top_k": 5}, headers=doctor).json["data"]
    assert len(data["top_predictions"]) == 5
    assert data["unknown_symptoms"] == ["unicorn"]
    assert len(data["warnings"]) == 2  # unknown symptom + too few symptoms


def test_predict_only_unknown_symptoms_is_422(client, doctor):
    res = client.post("/api/predictions", json={"symptoms": ["telepathy", "levitation"]}, headers=doctor)
    assert res.status_code == 422
    assert res.json["error"]["code"] == "NO_KNOWN_SYMPTOMS"
    assert res.json["error"]["details"]["unknown_symptoms"] == ["telepathy", "levitation"]


def test_predict_malformed_input(client, doctor):
    for body in ({}, {"symptoms": "   "}, {"symptoms": [{"a": 1}]}, {"symptoms": ["cough"], "top_k": 0}, {"symptoms": ["cough"], "top_k": "3"}):
        assert client.post("/api/predictions", json=body, headers=doctor).status_code == 400, body
    assert client.post("/api/predictions", data="not json", headers=doctor).status_code == 400


def test_model_card_is_public(client):
    res = client.get("/api/model")
    assert res.status_code == 200
    data = res.json["data"]
    assert data["loaded"] is True
    assert data["algorithm"] == "RandomForestClassifier"
    assert "fever" in data["symptoms"]
    assert "Disease" not in data["classes"]  # regression: old CSV header bug
    assert len(data["classes"]) == 10
    assert data["evaluation"]["holdout"]["accuracy"] > 0.8


def test_missing_model_degrades_gracefully(tmp_path):
    app = create_app("testing", {"MODEL_DIR": tmp_path})
    with app.app_context():
        user = User(username="frontdesk1", full_name="Sarah Johnson", role="frontdesk")
        user.set_password("desk-pass-123")
        db.session.add(user)
        db.session.commit()
    client = app.test_client()
    headers = {"Authorization": "Bearer " + client.post("/api/auth/login", json={"username": "frontdesk1", "password": "desk-pass-123"}).json["data"]["token"]}

    assert client.get("/api/health").json["data"]["status"] == "degraded"
    assert client.get("/api/model").json["data"]["loaded"] is False
    res = client.post("/api/predictions", json={"symptoms": ["cough"]}, headers=headers)
    assert res.status_code == 503 and res.json["error"]["code"] == "MODEL_UNAVAILABLE"

    # Booking still works; the prediction is recorded as unavailable.
    res = client.post(
        "/api/appointments",
        json={"patient": {"full_name": "Asha Verma", "phone": "9876543210"}, "scheduled_at": future(), "appointment_type": "consultation", "symptoms": ["cough"]},
        headers=headers,
    )
    assert res.status_code == 201
    assert res.json["data"]["prediction"]["status"] == "model_unavailable"
