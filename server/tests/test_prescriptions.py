import io

from pypdf import PdfReader


def _prescribe(client, headers, appointment_id, **overrides):
    payload = {
        "appointment_id": appointment_id,
        "diagnosis": "Common cold",
        "medications": [
            {"name": "Cetirizine 10 mg", "dosage": "1 tablet", "instructions": "At night for 5 days"},
            {"name": "Steam inhalation", "instructions": "Twice daily"},
        ],
        "notes": "Review in one week if not improving.",
        **overrides,
    }
    return client.post("/api/prescriptions", json=payload, headers=headers)


def test_doctor_writes_prescription(client, doctor, make_appointment):
    appointment = make_appointment()
    res = _prescribe(client, doctor, appointment["id"])
    assert res.status_code == 201
    data = res.json["data"]
    assert data["doctor"]["full_name"] == "Dr. Evelyn Reed"
    assert data["medications"][1] == {"name": "Steam inhalation", "dosage": None, "instructions": "Twice daily"}

    detail = client.get(f"/api/appointments/{appointment['id']}", headers=doctor).json["data"]
    assert detail["prescription_count"] == 1
    assert detail["prescriptions"][0]["id"] == data["id"]


def test_doctor_identity_comes_from_token_not_body(client, doctor, make_appointment):
    appointment = make_appointment()
    res = _prescribe(client, doctor, appointment["id"], doctor_name="Dr. Somebody Else")
    assert res.json["data"]["doctor"]["username"] == "doctor1"


def test_prescription_validation(client, doctor, make_appointment):
    appointment = make_appointment()
    assert _prescribe(client, doctor, appointment["id"], medications=[]).status_code == 400
    assert _prescribe(client, doctor, appointment["id"], diagnosis="").status_code == 400
    assert _prescribe(client, doctor, appointment["id"], medications=[{"dosage": "5 mg"}]).status_code == 400
    assert _prescribe(client, doctor, appointment["id"], medications=["aspirin"]).status_code == 400
    assert _prescribe(client, doctor, 999).status_code == 404


def test_cannot_prescribe_for_cancelled_appointment(client, doctor, make_appointment):
    appointment = make_appointment()
    client.patch(f"/api/appointments/{appointment['id']}", json={"status": "cancelled"}, headers=doctor)
    res = _prescribe(client, doctor, appointment["id"])
    assert res.status_code == 409


def test_pdf_download(client, doctor, frontdesk, make_appointment):
    appointment = make_appointment(name="Asha Verma")
    rx = _prescribe(client, doctor, appointment["id"]).json["data"]

    res = client.get(f"/api/prescriptions/{rx['id']}/pdf", headers=frontdesk)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF")
    disposition = res.headers["Content-Disposition"]
    assert f"prescription_RX-{rx['id']:06d}.pdf" in disposition
    assert "Asha" not in disposition  # no patient data in filenames

    text = "".join(page.extract_text() for page in PdfReader(io.BytesIO(res.data)).pages)
    for expected in ("Asha Verma", "Dr. Evelyn Reed", "Cetirizine 10 mg", "Common cold", "not part of this prescription", "Not a valid medical prescription"):
        assert expected in text
    assert "Dr. Dr." not in text  # regression: the old PDF double-prefixed the title


def test_pdf_escapes_markup_in_user_input(client, doctor, make_appointment):
    appointment = make_appointment()
    rx = _prescribe(client, doctor, appointment["id"], diagnosis="Flu <font size=90>&amp; </b>").json["data"]
    res = client.get(f"/api/prescriptions/{rx['id']}/pdf", headers=doctor)
    assert res.status_code == 200
    text = PdfReader(io.BytesIO(res.data)).pages[0].extract_text()
    assert "<font size=90>" in text


def test_long_prescription_paginates(client, doctor, make_appointment):
    appointment = make_appointment()
    meds = [{"name": f"Medication {i}", "dosage": "10 mg", "instructions": "Take with food. " * 8} for i in range(20)]
    rx = _prescribe(client, doctor, appointment["id"], medications=meds).json["data"]
    res = client.get(f"/api/prescriptions/{rx['id']}/pdf", headers=doctor)
    assert len(PdfReader(io.BytesIO(res.data)).pages) >= 2


def test_pdf_not_found(client, doctor):
    assert client.get("/api/prescriptions/42/pdf", headers=doctor).status_code == 404
