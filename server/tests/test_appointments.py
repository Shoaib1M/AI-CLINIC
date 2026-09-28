from .conftest import future


def test_create_appointment_runs_prediction(make_appointment):
    data = make_appointment()
    assert data["status"] == "pending"
    assert data["patient"]["full_name"] == "Asha Verma"
    assert data["symptoms"] == ["cough", "runny nose", "sneezing", "sore throat", "congestion"]
    prediction = data["prediction"]
    assert prediction["status"] == "ok"
    assert prediction["predicted_disease"] == "Common Cold"
    assert 0 < prediction["confidence"] <= 1
    assert prediction["reference_treatments"] == ["Antihistamines", "Decongestants", "Rest & Fluids"]
    assert data["created_by"]["username"] == "frontdesk1"


def test_symptoms_are_normalised_and_unknown_ones_flagged(make_appointment):
    data = make_appointment(symptoms=[" Fever ", "COUGH", "body aches", "fever", "telepathy"])
    assert data["symptoms"] == ["fever", "cough", "body ache", "telepathy"]
    assert data["prediction"]["unknown_symptoms"] == ["telepathy"]
    assert data["prediction"]["recognized_symptoms"] == ["fever", "cough", "body ache"]


def test_only_unknown_symptoms_still_books_without_prediction(make_appointment):
    data = make_appointment(symptoms=["back pain", "insomnia"])
    assert data["prediction"]["status"] == "no_known_symptoms"
    assert data["prediction"]["predicted_disease"] is None


def test_comma_separated_symptoms_accepted_for_compatibility(make_appointment):
    data = make_appointment(symptoms="fever, chills, vomiting")
    assert data["symptoms"] == ["fever", "chills", "vomiting"]


def test_returning_patient_is_reused(make_appointment):
    first = make_appointment(name="Asha Verma")
    second = make_appointment(name="asha verma")
    assert first["patient"]["id"] == second["patient"]["id"]
    different_phone = make_appointment(name="Asha Verma", phone="+91 91111 11111")
    assert different_phone["patient"]["id"] != first["patient"]["id"]


def test_create_for_existing_patient_id(client, frontdesk, make_appointment):
    first = make_appointment()
    res = client.post(
        "/api/appointments",
        json={"patient_id": first["patient"]["id"], "scheduled_at": future(3), "appointment_type": "follow_up", "symptoms": ["cough"]},
        headers=frontdesk,
    )
    assert res.status_code == 201
    assert res.json["data"]["patient"]["id"] == first["patient"]["id"]

    res = client.post(
        "/api/appointments",
        json={"patient_id": 999, "scheduled_at": future(), "appointment_type": "follow_up", "symptoms": ["cough"]},
        headers=frontdesk,
    )
    assert res.status_code == 404


def test_validation_reports_every_bad_field(client, frontdesk):
    res = client.post(
        "/api/appointments",
        json={
            "patient": {"full_name": "R2-D2", "phone": "12"},
            "scheduled_at": "2001-01-01T09:00",
            "appointment_type": "spa",
            "symptoms": [],
        },
        headers=frontdesk,
    )
    assert res.status_code == 400
    assert res.json["error"]["code"] == "INVALID_INPUT"
    assert set(res.json["error"]["details"]) == {
        "patient.full_name", "patient.phone", "scheduled_at", "appointment_type", "symptoms",
    }


def test_rejects_malformed_symptoms_and_dates(client, frontdesk):
    base = {"patient": {"full_name": "Asha Verma", "phone": "9876543210"}, "appointment_type": "consultation"}
    cases = [
        {"scheduled_at": "tomorrow", "symptoms": ["cough"]},
        {"scheduled_at": future(), "symptoms": [1, 2]},
        {"scheduled_at": future(), "symptoms": ["<script>alert(1)</script>"]},
        {"scheduled_at": future(), "symptoms": [f"s{i}" for i in range(20)]},
        {"scheduled_at": future(days=400), "symptoms": ["cough"]},
    ]
    for case in cases:
        res = client.post("/api/appointments", json={**base, **case}, headers=frontdesk)
        assert res.status_code == 400, case


def test_get_appointment_includes_details(client, doctor, make_appointment):
    first = make_appointment()
    second = make_appointment(symptoms=["fever", "chills"])
    res = client.get(f"/api/appointments/{second['id']}", headers=doctor)
    assert res.status_code == 200
    assert res.json["data"]["prescriptions"] == []
    assert [v["id"] for v in res.json["data"]["visit_history"]] == [first["id"]]
    assert client.get("/api/appointments/999", headers=doctor).status_code == 404


def test_list_filter_search_sort_paginate(client, doctor, make_appointment):
    make_appointment(name="Asha Verma")
    make_appointment(name="Bina Rao", phone="+91 90000 00002", symptoms=["fever", "chills", "vomiting", "nausea", "body ache"])
    make_appointment(name="Chetan Das", phone="+91 90000 00003", symptoms=["headache", "nausea", "blurred vision", "dizziness"])

    res = client.get("/api/appointments?per_page=2&sort=patient_name&order=asc", headers=doctor)
    assert res.json["meta"] == {"page": 1, "per_page": 2, "total": 3, "pages": 2}
    assert [a["patient"]["full_name"] for a in res.json["data"]] == ["Asha Verma", "Bina Rao"]

    by_name = client.get("/api/appointments?q=chetan", headers=doctor).json["data"]
    assert [a["patient"]["full_name"] for a in by_name] == ["Chetan Das"]

    by_symptom = client.get("/api/appointments?q=vomiting", headers=doctor).json["data"]
    assert [a["patient"]["full_name"] for a in by_symptom] == ["Bina Rao"]

    disease = by_symptom[0]["prediction"]["predicted_disease"]
    by_disease = client.get(f"/api/appointments?disease={disease}", headers=doctor).json["data"]
    assert all(a["prediction"]["predicted_disease"] == disease for a in by_disease)

    # LIKE wildcards in the search box are treated literally.
    assert client.get("/api/appointments?q=%25", headers=doctor).json["meta"]["total"] == 0

    assert client.get("/api/appointments?status=weird", headers=doctor).status_code == 400
    assert client.get("/api/appointments?per_page=1000", headers=doctor).status_code == 400


def test_doctor_completes_and_frontdesk_cancels(client, doctor, frontdesk, make_appointment):
    a, b = make_appointment(), make_appointment(name="Bina Rao")

    res = client.patch(f"/api/appointments/{a['id']}", json={"status": "completed"}, headers=doctor)
    assert res.status_code == 200 and res.json["data"]["status"] == "completed"

    res = client.patch(f"/api/appointments/{b['id']}", json={"status": "cancelled"}, headers=frontdesk)
    assert res.status_code == 200 and res.json["data"]["status"] == "cancelled"

    status_filter = client.get("/api/appointments?status=cancelled", headers=doctor).json["data"]
    assert [x["id"] for x in status_filter] == [b["id"]]


def test_status_rules(client, doctor, frontdesk, make_appointment):
    a = make_appointment()
    # Front desk cannot mark a visit completed.
    assert client.patch(f"/api/appointments/{a['id']}", json={"status": "completed"}, headers=frontdesk).status_code == 403
    client.patch(f"/api/appointments/{a['id']}", json={"status": "completed"}, headers=doctor)
    # Completed is final.
    res = client.patch(f"/api/appointments/{a['id']}", json={"status": "cancelled"}, headers=doctor)
    assert res.status_code == 409 and res.json["error"]["code"] == "INVALID_STATUS_TRANSITION"
    # Completed visits cannot be rescheduled.
    res = client.patch(f"/api/appointments/{a['id']}", json={"scheduled_at": future(5)}, headers=frontdesk)
    assert res.status_code == 409


def test_cancelled_can_be_reinstated_and_rescheduled(client, frontdesk, make_appointment):
    a = make_appointment()
    client.patch(f"/api/appointments/{a['id']}", json={"status": "cancelled"}, headers=frontdesk)
    res = client.patch(f"/api/appointments/{a['id']}", json={"status": "pending"}, headers=frontdesk)
    assert res.json["data"]["status"] == "pending"
    new_time = future(4, hour=15)
    res = client.patch(
        f"/api/appointments/{a['id']}", json={"scheduled_at": new_time, "appointment_type": "follow_up"}, headers=frontdesk
    )
    assert res.status_code == 200
    assert res.json["data"]["scheduled_at"] == new_time
    assert res.json["data"]["appointment_type"] == "follow_up"


def test_update_rejects_unknown_fields(client, doctor, make_appointment):
    a = make_appointment()
    res = client.patch(f"/api/appointments/{a['id']}", json={"symptoms": ["x"], "id": 5}, headers=doctor)
    assert res.status_code == 400
    assert client.patch(f"/api/appointments/{a['id']}", json={}, headers=doctor).status_code == 400
    assert client.patch("/api/appointments/999", json={"status": "cancelled"}, headers=doctor).status_code == 404


def test_stats(client, doctor, make_appointment):
    a = make_appointment()
    make_appointment(name="Bina Rao")
    client.patch(f"/api/appointments/{a['id']}", json={"status": "completed"}, headers=doctor)
    data = client.get("/api/appointments/stats", headers=doctor).json["data"]
    assert data["total_appointments"] == 2
    assert data["by_status"] == {"pending": 1, "completed": 1, "cancelled": 0}
    assert data["total_patients"] == 2
    assert data["top_predicted_diseases"][0] == {"disease": "Common Cold", "count": 2}


def test_patient_search(client, frontdesk, make_appointment):
    make_appointment(name="Asha Verma", phone="+91 98765 43210")
    make_appointment(name="Bina Rao", phone="+91 90000 00002")
    assert client.get("/api/patients?q=a", headers=frontdesk).json["data"] == []  # too short
    results = client.get("/api/patients?q=asha", headers=frontdesk).json["data"]
    assert [p["full_name"] for p in results] == ["Asha Verma"]
    assert results[0]["visit_count"] == 1
    assert [p["full_name"] for p in client.get("/api/patients?q=00002", headers=frontdesk).json["data"]] == ["Bina Rao"]


def test_search_treats_regex_characters_literally(client, doctor, make_appointment):
    make_appointment(name="Asha Verma")
    for q in (".*", "(", "a|b", "[a-z]+"):
        res = client.get("/api/appointments", query_string={"q": q}, headers=doctor)
        assert res.status_code == 200
        assert res.json["meta"]["total"] == 0, q


def test_confidence_sort_puts_missing_predictions_last(client, doctor, make_appointment):
    make_appointment(name="No Prediction", phone="+91 90000 00009", symptoms=["back pain"])
    make_appointment(name="Asha Verma")
    for order in ("asc", "desc"):
        rows = client.get(f"/api/appointments?sort=confidence&order={order}", headers=doctor).json["data"]
        assert rows[-1]["patient"]["full_name"] == "No Prediction", order


def test_prescription_count_tracks_new_prescriptions(client, doctor, make_appointment):
    a = make_appointment()
    for _ in range(2):
        client.post(
            "/api/prescriptions",
            json={"appointment_id": a["id"], "diagnosis": "Common cold", "medications": [{"name": "Rest"}]},
            headers=doctor,
        )
    listed = client.get("/api/appointments", headers=doctor).json["data"][0]
    assert listed["prescription_count"] == 2


def test_unreachable_database_starts_degraded_and_returns_503():
    from app import create_app

    # Nothing listens on port 1: the real PyMongo client times out quickly.
    app = create_app("testing", {"MONGODB_URI": "mongodb://127.0.0.1:1", "MONGODB_TIMEOUT_MS": 200})
    client = app.test_client()

    health = client.get("/api/health")
    assert health.status_code == 503
    assert health.json["data"]["database"] == "unavailable"

    res = client.post("/api/auth/login", json={"username": "doctor1", "password": "doctor-pass-123"})
    assert res.status_code == 503
    assert res.json["error"]["code"] == "DATABASE_UNAVAILABLE"
    assert "127.0.0.1" not in res.get_data(as_text=True)  # no connection details leak to clients
