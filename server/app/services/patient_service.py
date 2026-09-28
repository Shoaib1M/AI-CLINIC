"""Patient lookup and creation."""

import logging
import re

from pymongo.errors import DuplicateKeyError

from ..errors import NotFound
from ..extensions import mongo, next_id
from ..models import patient_to_dict, utcnow

logger = logging.getLogger(__name__)

SEARCH_CANDIDATES = 50


def get_patient(patient_id: int) -> dict:
    patient = mongo.db.patients.find_one({"_id": patient_id})
    if patient is None:
        raise NotFound("Patient not found.", code="PATIENT_NOT_FOUND")
    return patient


def find_or_create_patient(full_name: str, phone: str) -> dict:
    """Reuse an existing record with the same name (case-insensitive) and phone, else create one."""
    key = {"full_name_lower": full_name.lower(), "phone": phone}
    existing = mongo.db.patients.find_one(key)
    if existing:
        return existing

    now = utcnow()
    patient = {"_id": next_id("patients"), "full_name": full_name, **key, "created_at": now, "updated_at": now}
    try:
        mongo.db.patients.insert_one(patient)
    except DuplicateKeyError:
        # A concurrent request registered the same person first; use that record.
        return mongo.db.patients.find_one(key)
    logger.info("patient_created", extra={"patient_id": patient["_id"]})
    return patient


def search_patients(query: str, limit: int = 10) -> list[dict]:
    """Case-insensitive match on name or phone, most recently seen first."""
    needle = re.escape(query.strip().lower())  # user input is matched literally, never as a regex
    if not needle:
        return []
    candidates = list(
        mongo.db.patients.find(
            {"$or": [{"full_name_lower": {"$regex": needle}}, {"phone": {"$regex": needle}}]}
        ).limit(SEARCH_CANDIDATES)
    )
    if not candidates:
        return []

    visits = {
        row["_id"]: row
        for row in mongo.db.appointments.aggregate(
            [
                {"$match": {"patient_id": {"$in": [p["_id"] for p in candidates]}}},
                {"$group": {"_id": "$patient_id", "visits": {"$sum": 1}, "last_visit": {"$max": "$scheduled_at"}}},
            ]
        )
    }

    def sort_key(patient):
        last = visits.get(patient["_id"], {}).get("last_visit")
        # Patients with visits first (most recent first), then alphabetical.
        return (last is None, -last.timestamp() if last else 0, patient["full_name_lower"])

    results = []
    for patient in sorted(candidates, key=sort_key)[:limit]:
        stats = visits.get(patient["_id"], {})
        last = stats.get("last_visit")
        results.append(
            {
                **patient_to_dict(patient),
                "last_visit": last.isoformat(timespec="minutes") if last else None,
                "visit_count": stats.get("visits", 0),
            }
        )
    return results
