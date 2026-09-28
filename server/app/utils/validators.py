"""Request validation.

Each `validate_*` function takes untrusted input and either returns a cleaned
dict or raises ValidationError with per-field messages in `details`, e.g.

    {"error": {"code": "INVALID_INPUT", "message": "...",
               "details": {"patient.phone": "Enter a valid phone number."}}}

The frontend validates too, but only as a convenience: these checks are the
ones that count.
"""

import re
import unicodedata
from datetime import date, datetime, timedelta

from ..errors import ValidationError
from ..ml.preprocessing import normalize_symptoms
from ..models import APPOINTMENT_TYPES, STATUSES

PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")
SYMPTOM_RE = re.compile(r"^[a-z0-9 '/().&]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{3,50}$")

MAX_SYMPTOMS = 15
MAX_SYMPTOM_LENGTH = 60
MAX_MEDICATIONS = 20
SORT_FIELDS = ("scheduled_at", "created_at", "patient_name", "confidence")
MAX_BOOKING_HORIZON = timedelta(days=365)


def is_valid_person_name(name: str) -> bool:
    """Letters from any script (plus combining marks, e.g. Devanagari vowel
    signs), spaces, periods, apostrophes and hyphens; must start with a letter."""
    if not name or not unicodedata.category(name[0]).startswith("L"):
        return False
    return all(unicodedata.category(ch)[0] in "LM" or ch in " .'-" for ch in name)


class _Errors:
    """Collects field errors so the client gets all of them in one response."""

    def __init__(self):
        self.fields: dict[str, str] = {}

    def add(self, field: str, message: str) -> None:
        self.fields.setdefault(field, message)

    def raise_if_any(self, message: str = "The request contains invalid data.") -> None:
        if self.fields:
            raise ValidationError(message, details=self.fields)


def require_json_object(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object.", code="INVALID_JSON")
    return payload


def _clean_str(value, field: str, errors: _Errors, *, required=True, min_len=1, max_len=200):
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            errors.add(field, "This field is required.")
        return None
    if not isinstance(value, str):
        errors.add(field, "Must be a string.")
        return None
    value = " ".join(value.split())
    if len(value) < min_len:
        errors.add(field, f"Must be at least {min_len} characters.")
    elif len(value) > max_len:
        errors.add(field, f"Must be at most {max_len} characters.")
    return value


def _positive_int(value, field: str, errors: _Errors):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        errors.add(field, "Must be a positive integer.")
        return None
    return value


# --- auth -------------------------------------------------------------------

def validate_login(payload) -> dict:
    payload = require_json_object(payload)
    errors = _Errors()
    username = payload.get("username")
    password = payload.get("password")
    if not isinstance(username, str) or not username.strip():
        errors.add("username", "Username is required.")
    if not isinstance(password, str) or not password:
        errors.add("password", "Password is required.")
    errors.raise_if_any()
    return {"username": username.strip(), "password": password}


def validate_new_user(username: str, full_name: str, role: str, password: str) -> None:
    errors = _Errors()
    if not USERNAME_RE.match(username or ""):
        errors.add("username", "3–50 characters: letters, digits, '.', '_' or '-'.")
    _clean_str(full_name, "full_name", errors, min_len=2, max_len=100)
    if role not in ("doctor", "frontdesk"):
        errors.add("role", "Must be 'doctor' or 'frontdesk'.")
    if not isinstance(password, str) or len(password) < 8:
        errors.add("password", "Must be at least 8 characters.")
    errors.raise_if_any()


# --- symptoms ---------------------------------------------------------------

def validate_symptoms(value, errors: _Errors | None = None, field: str = "symptoms") -> list[str]:
    """Accept a list of strings (preferred) or a comma-separated string."""
    own_errors = errors is None
    errors = errors or _Errors()

    if isinstance(value, str):
        value = value.split(",")
    if not isinstance(value, list) or not all(isinstance(s, str) for s in value):
        errors.add(field, "Symptoms must be a list of strings.")
        if own_errors:
            errors.raise_if_any()
        return []

    symptoms = normalize_symptoms(value)
    if not symptoms:
        errors.add(field, "At least one symptom is required.")
    elif len(symptoms) > MAX_SYMPTOMS:
        errors.add(field, f"At most {MAX_SYMPTOMS} symptoms are allowed.")
    else:
        for symptom in symptoms:
            if len(symptom) > MAX_SYMPTOM_LENGTH or not SYMPTOM_RE.match(symptom):
                errors.add(field, f"Invalid symptom: '{symptom[:MAX_SYMPTOM_LENGTH]}'.")
                break

    if own_errors:
        errors.raise_if_any()
    return symptoms


def validate_prediction_request(payload) -> dict:
    payload = require_json_object(payload)
    errors = _Errors()
    symptoms = validate_symptoms(payload.get("symptoms"), errors)
    top_k = payload.get("top_k", 3)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        errors.add("top_k", "Must be an integer between 1 and 10.")
    errors.raise_if_any()
    return {"symptoms": symptoms, "top_k": top_k}


# --- appointments -----------------------------------------------------------

def _parse_scheduled_at(value, errors: _Errors, now: datetime):
    if not isinstance(value, str) or not value.strip():
        errors.add("scheduled_at", "Appointment date and time are required.")
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        errors.add("scheduled_at", "Use the format YYYY-MM-DDTHH:MM.")
        return None
    if parsed.tzinfo is not None:
        errors.add("scheduled_at", "Use local clinic time without a timezone offset.")
        return None
    if parsed.date() < now.date():
        errors.add("scheduled_at", "Appointments cannot be booked in the past.")
    elif parsed - now > MAX_BOOKING_HORIZON:
        errors.add("scheduled_at", "Appointments can be booked at most one year ahead.")
    return parsed.replace(second=0, microsecond=0)


def _appointment_type(value, errors: _Errors):
    if value not in APPOINTMENT_TYPES:
        errors.add("appointment_type", f"Must be one of: {', '.join(APPOINTMENT_TYPES)}.")
        return None
    return value


def _validate_patient(value, errors: _Errors) -> dict | None:
    if not isinstance(value, dict):
        errors.add("patient", "Patient details are required.")
        return None
    name = _clean_str(value.get("full_name"), "patient.full_name", errors, min_len=2, max_len=100)
    if name and not is_valid_person_name(name):
        errors.add("patient.full_name", "Use letters, spaces, apostrophes, hyphens or periods only.")
    phone = _clean_str(value.get("phone"), "patient.phone", errors, max_len=20)
    if phone:
        digits = re.sub(r"\D", "", phone)
        if not PHONE_RE.match(phone) or not 7 <= len(digits) <= 15:
            errors.add("patient.phone", "Enter a valid phone number (7–15 digits).")
    return {"full_name": name, "phone": phone}


def validate_appointment_create(payload, now: datetime | None = None) -> dict:
    """Either `patient_id` (existing patient) or `patient` (new patient) is required."""
    payload = require_json_object(payload)
    now = now or datetime.now()
    errors = _Errors()

    patient_id = payload.get("patient_id")
    patient = None
    if patient_id is not None:
        patient_id = _positive_int(patient_id, "patient_id", errors)
    else:
        patient = _validate_patient(payload.get("patient"), errors)

    cleaned = {
        "patient_id": patient_id,
        "patient": patient,
        "scheduled_at": _parse_scheduled_at(payload.get("scheduled_at"), errors, now),
        "appointment_type": _appointment_type(payload.get("appointment_type"), errors),
        "symptoms": validate_symptoms(payload.get("symptoms"), errors),
    }
    errors.raise_if_any()
    return cleaned


UPDATABLE_FIELDS = {"status", "scheduled_at", "appointment_type"}


def validate_appointment_update(payload, now: datetime | None = None) -> dict:
    payload = require_json_object(payload)
    now = now or datetime.now()
    errors = _Errors()

    unknown = set(payload) - UPDATABLE_FIELDS
    if unknown:
        errors.add("body", f"Unsupported field(s): {', '.join(sorted(unknown))}.")
    if not set(payload) & UPDATABLE_FIELDS:
        errors.add("body", f"Provide at least one of: {', '.join(sorted(UPDATABLE_FIELDS))}.")

    cleaned = {}
    if "status" in payload:
        if payload["status"] not in STATUSES:
            errors.add("status", f"Must be one of: {', '.join(STATUSES)}.")
        cleaned["status"] = payload["status"]
    if "scheduled_at" in payload:
        cleaned["scheduled_at"] = _parse_scheduled_at(payload["scheduled_at"], errors, now)
    if "appointment_type" in payload:
        cleaned["appointment_type"] = _appointment_type(payload["appointment_type"], errors)
    errors.raise_if_any()
    return cleaned


def _parse_date(value, field, errors) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        errors.add(field, "Use the format YYYY-MM-DD.")
        return None


def _query_int(value, field, errors, default, low, high):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except ValueError:
        errors.add(field, "Must be an integer.")
        return default
    if not low <= number <= high:
        errors.add(field, f"Must be between {low} and {high}.")
    return number


def validate_list_query(args) -> dict:
    errors = _Errors()
    status = args.get("status") or None
    if status and status not in STATUSES:
        errors.add("status", f"Must be one of: {', '.join(STATUSES)}.")
    sort = args.get("sort") or "scheduled_at"
    if sort not in SORT_FIELDS:
        errors.add("sort", f"Must be one of: {', '.join(SORT_FIELDS)}.")
    order = (args.get("order") or "desc").lower()
    if order not in ("asc", "desc"):
        errors.add("order", "Must be 'asc' or 'desc'.")
    query = {
        "q": (args.get("q") or "").strip()[:100] or None,
        "status": status,
        "disease": (args.get("disease") or "").strip()[:100] or None,
        "date_from": _parse_date(args.get("date_from"), "date_from", errors),
        "date_to": _parse_date(args.get("date_to"), "date_to", errors),
        "sort": sort,
        "order": order,
        "page": _query_int(args.get("page"), "page", errors, 1, 1, 10_000),
        "per_page": _query_int(args.get("per_page"), "per_page", errors, 20, 1, 100),
    }
    errors.raise_if_any("Invalid query parameters.")
    return query


# --- prescriptions ----------------------------------------------------------

def validate_prescription(payload) -> dict:
    payload = require_json_object(payload)
    errors = _Errors()

    appointment_id = _positive_int(payload.get("appointment_id"), "appointment_id", errors)
    diagnosis = _clean_str(payload.get("diagnosis"), "diagnosis", errors, min_len=2, max_len=200)
    notes = _clean_str(payload.get("notes"), "notes", errors, required=False, max_len=2000)

    medications = []
    raw_meds = payload.get("medications")
    if not isinstance(raw_meds, list) or not raw_meds:
        errors.add("medications", "Add at least one medication or instruction.")
    elif len(raw_meds) > MAX_MEDICATIONS:
        errors.add("medications", f"At most {MAX_MEDICATIONS} medications are allowed.")
    else:
        for i, med in enumerate(raw_meds):
            prefix = f"medications[{i}]"
            if not isinstance(med, dict):
                errors.add(prefix, "Each medication must be an object.")
                continue
            medications.append(
                {
                    "name": _clean_str(med.get("name"), f"{prefix}.name", errors, max_len=100),
                    "dosage": _clean_str(med.get("dosage"), f"{prefix}.dosage", errors, required=False, max_len=100),
                    "instructions": _clean_str(
                        med.get("instructions"), f"{prefix}.instructions", errors, required=False, max_len=300
                    ),
                }
            )

    errors.raise_if_any()
    return {"appointment_id": appointment_id, "diagnosis": diagnosis, "medications": medications, "notes": notes}
