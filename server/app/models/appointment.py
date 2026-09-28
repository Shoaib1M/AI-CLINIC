"""Appointments (collection `appointments`).

    {_id: int, patient_id, patient_name, patient_name_lower, patient_phone,
     scheduled_at, appointment_type, status, symptoms: [str],
     prediction: {...embedded AI suggestion...}, prescription_count,
     created_by_id, created_at, updated_at}

`patient_name`/`patient_phone` are a denormalised copy of the patient so the
queue can be searched and sorted by name with a single-collection query. That
is safe because patient details are never edited through the API.
`prescription_count` is kept in sync with `$inc` when a prescription is added.
"""

from .base import iso
from .patient import patient_to_dict
from .prediction import prediction_to_dict

APPOINTMENT_TYPES = ("regular_checkup", "follow_up", "consultation", "emergency")
STATUSES = ("pending", "completed", "cancelled")


def appointment_to_dict(doc: dict, patient_doc: dict, *, created_by: dict | None = None,
                        prescriptions: list[dict] | None = None, include_details: bool = False) -> dict:
    data = {
        "id": doc["_id"],
        "patient": patient_to_dict(patient_doc),
        "scheduled_at": doc["scheduled_at"].isoformat(timespec="minutes"),
        "appointment_type": doc["appointment_type"],
        "status": doc["status"],
        "symptoms": list(doc.get("symptoms") or []),
        "prediction": prediction_to_dict(doc.get("prediction")),
        "prescription_count": doc.get("prescription_count", 0),
        "created_at": iso(doc.get("created_at")),
        "updated_at": iso(doc.get("updated_at")),
    }
    if include_details:
        data["created_by"] = created_by
        data["prescriptions"] = prescriptions or []
    return data
