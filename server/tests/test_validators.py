from datetime import datetime

import pytest

from app.errors import ValidationError
from app.utils.validators import validate_appointment_create, validate_symptoms

NOW = datetime(2030, 5, 10, 12, 0)


def _payload(**overrides):
    return {
        "patient": {"full_name": "Asha Verma", "phone": "+91 98765 43210"},
        "scheduled_at": "2030-05-10T09:00",
        "appointment_type": "consultation",
        "symptoms": ["cough"],
        **overrides,
    }


def test_same_day_booking_allowed_even_if_hour_passed():
    assert validate_appointment_create(_payload(), now=NOW)["scheduled_at"] == datetime(2030, 5, 10, 9, 0)


@pytest.mark.parametrize("name", ["José Álvarez", "O'Brien", "Anne-Marie Li", "Dr. K. Rao", "राहुल"])
def test_accepts_international_names(name):
    validate_appointment_create(_payload(patient={"full_name": name, "phone": "9876543210"}), now=NOW)


@pytest.mark.parametrize("phone", ["12345", "phone", "+91 98765 43210 99999 1", "+1 (555) 12a4567"])
def test_rejects_bad_phones(phone):
    with pytest.raises(ValidationError) as exc:
        validate_appointment_create(_payload(patient={"full_name": "Asha", "phone": phone}), now=NOW)
    assert "patient.phone" in exc.value.details


def test_rejects_timezone_offsets():
    with pytest.raises(ValidationError):
        validate_appointment_create(_payload(scheduled_at="2030-05-11T09:00+05:30"), now=NOW)


def test_symptom_list_cleaning():
    assert validate_symptoms(["Fever", "fever", "  sore   throat "]) == ["fever", "sore throat"]
    assert validate_symptoms("fever,cough,,") == ["fever", "cough"]
    with pytest.raises(ValidationError):
        validate_symptoms(None)
