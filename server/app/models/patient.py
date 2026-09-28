"""Patients (collection `patients`).

    {_id: int, full_name, full_name_lower, phone, created_at, updated_at}

A unique index on (full_name_lower, phone) means one person is one record;
phone alone is not unique because family members often share a number.
"""

from .base import iso


def patient_to_dict(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "full_name": doc["full_name"],
        "phone": doc["phone"],
        "created_at": iso(doc.get("created_at")),
    }
