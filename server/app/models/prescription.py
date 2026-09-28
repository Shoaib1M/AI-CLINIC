"""Doctor-authored prescriptions (collection `prescriptions`).

    {_id: int, appointment_id, doctor_id, diagnosis,
     medications: [{name, dosage, instructions}], notes, created_at, updated_at}

A separate collection (not embedded in the appointment) because prescriptions
have their own identity and URL (/api/prescriptions/:id/pdf) and a visit may
accumulate several revisions.
"""

from .base import iso
from .user import user_to_dict


def prescription_to_dict(doc: dict, doctor_doc: dict | None) -> dict:
    return {
        "id": doc["_id"],
        "appointment_id": doc["appointment_id"],
        "doctor": user_to_dict(doctor_doc),
        "diagnosis": doc["diagnosis"],
        "medications": doc.get("medications") or [],
        "notes": doc.get("notes"),
        "created_at": iso(doc.get("created_at")),
    }
