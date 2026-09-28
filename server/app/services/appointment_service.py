"""Appointment use-cases: create, list/filter, fetch, update status, stats."""

import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from pymongo import ASCENDING, DESCENDING, ReturnDocument

from ..errors import Conflict, NotFound, PermissionDenied
from ..extensions import mongo, next_id
from ..models import STATUSES, User, appointment_to_dict, prescription_to_dict, user_to_dict, utcnow
from . import patient_service, prediction_service

logger = logging.getLogger(__name__)

# Allowed status changes. "completed" is final; a cancelled visit can be reinstated.
TRANSITIONS = {
    "pending": {"completed", "cancelled"},
    "cancelled": {"pending"},
    "completed": set(),
}
# Front desk manages the schedule; only a doctor can mark a visit completed.
ROLE_STATUS_PERMISSIONS = {
    "doctor": {"pending", "completed", "cancelled"},
    "frontdesk": {"pending", "cancelled"},
}

SORT_FIELDS = {
    "scheduled_at": "scheduled_at",
    "created_at": "created_at",
    "patient_name": "patient_name_lower",
    "confidence": "prediction.confidence",
}


@dataclass
class Page:
    items: list[dict]
    page: int
    per_page: int
    total: int

    @property
    def pages(self) -> int:
        return math.ceil(self.total / self.per_page) if self.total else 0


def _patients_by_id(ids) -> dict[int, dict]:
    return {p["_id"]: p for p in mongo.db.patients.find({"_id": {"$in": list(set(ids))}})}


def _serialize_list(docs: list[dict]) -> list[dict]:
    patients = _patients_by_id(d["patient_id"] for d in docs)  # one query for the whole page
    return [appointment_to_dict(d, patients[d["patient_id"]]) for d in docs]


def get_appointment_doc(appointment_id: int) -> dict:
    doc = mongo.db.appointments.find_one({"_id": appointment_id})
    if doc is None:
        raise NotFound("Appointment not found.", code="APPOINTMENT_NOT_FOUND")
    return doc


def appointment_detail(doc: dict) -> dict:
    """Full representation: patient, creator and prescriptions (with prescribing doctors)."""
    patient = patient_service.get_patient(doc["patient_id"])
    prescriptions = list(mongo.db.prescriptions.find({"appointment_id": doc["_id"]}).sort("created_at", DESCENDING))
    user_ids = {rx["doctor_id"] for rx in prescriptions} | {doc.get("created_by_id")}
    users = {u["_id"]: u for u in mongo.db.users.find({"_id": {"$in": [i for i in user_ids if i is not None]}})}
    return appointment_to_dict(
        doc,
        patient,
        created_by=user_to_dict(users.get(doc.get("created_by_id"))),
        prescriptions=[prescription_to_dict(rx, users.get(rx["doctor_id"])) for rx in prescriptions],
        include_details=True,
    )


def create_appointment(data: dict, user: User) -> dict:
    if data["patient_id"] is not None:
        patient = patient_service.get_patient(data["patient_id"])
    else:
        patient = patient_service.find_or_create_patient(**data["patient"])

    now = utcnow()
    doc = {
        "_id": next_id("appointments"),
        "patient_id": patient["_id"],
        "patient_name": patient["full_name"],
        "patient_name_lower": patient["full_name_lower"],
        "patient_phone": patient["phone"],
        "scheduled_at": data["scheduled_at"],
        "appointment_type": data["appointment_type"],
        "status": "pending",
        "symptoms": data["symptoms"],
        "prediction": prediction_service.prediction_record_for(data["symptoms"]),
        "prescription_count": 0,
        "created_by_id": user.id,
        "created_at": now,
        "updated_at": now,
    }
    # One document holds the appointment and its AI suggestion, so this write is atomic.
    mongo.db.appointments.insert_one(doc)
    logger.info(
        "appointment_created",
        extra={"appointment_id": doc["_id"], "patient_id": patient["_id"], "prediction_status": doc["prediction"]["status"]},
    )
    return appointment_detail(doc)


def _build_filter(query: dict) -> dict:
    conditions = {}
    if query["q"]:
        needle = re.escape(query["q"].lower())  # literal match: ".*" or "%" in the search box match nothing special
        conditions["$or"] = [
            {"patient_name_lower": {"$regex": needle}},
            {"patient_phone": {"$regex": needle}},
            {"prediction.predicted_disease": {"$regex": needle, "$options": "i"}},
            {"symptoms": {"$regex": needle}},  # matches any element of the array
        ]
    if query["status"]:
        conditions["status"] = query["status"]
    if query["disease"]:
        conditions["prediction.predicted_disease"] = query["disease"]
    date_range = {}
    if query["date_from"]:
        date_range["$gte"] = datetime.combine(query["date_from"], time.min)
    if query["date_to"]:
        date_range["$lt"] = datetime.combine(query["date_to"] + timedelta(days=1), time.min)
    if date_range:
        conditions["scheduled_at"] = date_range
    return conditions


def list_appointments(query: dict) -> Page:
    conditions = _build_filter(query)
    field = SORT_FIELDS[query["sort"]]
    direction = ASCENDING if query["order"] == "asc" else DESCENDING
    skip = (query["page"] - 1) * query["per_page"]

    pipeline = [
        {"$match": conditions},
        # Rows without a value (e.g. no confidence because no prediction) always sort last.
        {"$addFields": {"_missing": {"$cond": [{"$eq": [{"$ifNull": [f"${field}", None]}, None]}, 1, 0]}}},
        {"$sort": {"_missing": ASCENDING, field: direction, "_id": DESCENDING}},
        {"$skip": skip},
        {"$limit": query["per_page"]},
    ]
    docs = list(mongo.db.appointments.aggregate(pipeline))
    total = mongo.db.appointments.count_documents(conditions)
    return Page(items=_serialize_list(docs), page=query["page"], per_page=query["per_page"], total=total)


def update_appointment(appointment_id: int, changes: dict, user: User) -> dict:
    doc = get_appointment_doc(appointment_id)

    new_status = changes.get("status")
    if new_status and new_status != doc["status"]:
        if new_status not in ROLE_STATUS_PERMISSIONS[user.role]:
            raise PermissionDenied(f"Your role cannot set status to '{new_status}'.")
        if new_status not in TRANSITIONS[doc["status"]]:
            raise Conflict(
                f"Cannot change status from '{doc['status']}' to '{new_status}'.",
                code="INVALID_STATUS_TRANSITION",
            )

    schedule_changes = {k: v for k, v in changes.items() if k in ("scheduled_at", "appointment_type")}
    if schedule_changes and doc["status"] != "pending":
        raise Conflict("Only pending appointments can be rescheduled.", code="APPOINTMENT_NOT_PENDING")

    old_status = doc["status"]
    # Guard on the status we validated against, so two concurrent updates can't
    # both apply a transition that is only valid from the original state.
    result = mongo.db.appointments.find_one_and_update(
        {"_id": appointment_id, "status": old_status},
        {"$set": {**changes, "updated_at": utcnow()}},
        return_document=ReturnDocument.AFTER,
    )
    if result is None:
        raise Conflict("The appointment was changed by someone else. Reload and try again.", code="CONCURRENT_UPDATE")
    logger.info(
        "appointment_updated",
        extra={
            "appointment_id": appointment_id,
            "fields": ",".join(sorted(changes)),
            "from_status": old_status,
            "to_status": result["status"],
            "user_id": user.id,
        },
    )
    return appointment_detail(result)


def visit_history(doc: dict, limit: int = 10) -> list[dict]:
    """Other appointments for the same patient (for the details page)."""
    others = (
        mongo.db.appointments.find({"patient_id": doc["patient_id"], "_id": {"$ne": doc["_id"]}})
        .sort("scheduled_at", DESCENDING)
        .limit(limit)
    )
    return [
        {
            "id": a["_id"],
            "scheduled_at": a["scheduled_at"].isoformat(timespec="minutes"),
            "appointment_type": a["appointment_type"],
            "status": a["status"],
            "predicted_disease": (a.get("prediction") or {}).get("predicted_disease"),
        }
        for a in others
    ]


def stats(today: date | None = None) -> dict:
    today = today or date.today()
    by_status = {
        row["_id"]: row["n"]
        for row in mongo.db.appointments.aggregate([{"$group": {"_id": "$status", "n": {"$sum": 1}}}])
    }
    start = datetime.combine(today, time.min)
    scheduled_today = mongo.db.appointments.count_documents(
        {"scheduled_at": {"$gte": start, "$lt": start + timedelta(days=1)}}
    )
    top = mongo.db.appointments.aggregate(
        [
            {"$match": {"prediction.predicted_disease": {"$ne": None}}},
            {"$group": {"_id": "$prediction.predicted_disease", "n": {"$sum": 1}}},
            {"$sort": {"n": DESCENDING, "_id": ASCENDING}},
            {"$limit": 5},
        ]
    )
    return {
        "total_appointments": sum(by_status.values()),
        "by_status": {status: by_status.get(status, 0) for status in STATUSES},
        "scheduled_today": scheduled_today,
        "total_patients": mongo.db.patients.count_documents({}),
        "top_predicted_diseases": [{"disease": row["_id"], "count": row["n"]} for row in top],
    }
