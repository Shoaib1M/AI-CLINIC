"""Appointment use-cases: create, list/filter, fetch, update status, stats."""

import logging
from datetime import date, datetime, time, timedelta

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import selectinload

from ..errors import Conflict, NotFound, PermissionDenied
from ..extensions import db
from ..models import STATUSES, Appointment, Patient, Prediction, User
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

_LOAD_OPTIONS = (
    selectinload(Appointment.patient),
    selectinload(Appointment.prediction),
    selectinload(Appointment.prescriptions),
)


def create_appointment(data: dict, user: User) -> Appointment:
    if data["patient_id"] is not None:
        patient = patient_service.get_patient(data["patient_id"])
    else:
        patient = patient_service.find_or_create_patient(**data["patient"])

    appointment = Appointment(
        patient=patient,
        scheduled_at=data["scheduled_at"],
        appointment_type=data["appointment_type"],
        symptoms=data["symptoms"],
        status="pending",
        created_by=user,
    )
    appointment.prediction = prediction_service.prediction_record_for(data["symptoms"])
    db.session.add(appointment)
    db.session.commit()
    logger.info(
        "appointment_created",
        extra={
            "appointment_id": appointment.id,
            "patient_id": patient.id,
            "prediction_status": appointment.prediction.status,
        },
    )
    return appointment


def get_appointment(appointment_id: int) -> Appointment:
    appointment = db.session.scalar(
        db.select(Appointment).options(*_LOAD_OPTIONS).where(Appointment.id == appointment_id)
    )
    if appointment is None:
        raise NotFound("Appointment not found.", code="APPOINTMENT_NOT_FOUND")
    return appointment


def list_appointments(query: dict):
    stmt = (
        db.select(Appointment)
        .join(Appointment.patient)
        .outerjoin(Appointment.prediction)
        .options(*_LOAD_OPTIONS)
    )

    if query["q"]:
        needle = query["q"].lower()
        stmt = stmt.where(
            or_(
                func.lower(Patient.full_name).contains(needle, autoescape=True),
                Patient.phone.contains(needle, autoescape=True),
                func.lower(Prediction.predicted_disease).contains(needle, autoescape=True),
                func.lower(cast(Appointment.symptoms, String)).contains(needle, autoescape=True),
            )
        )
    if query["status"]:
        stmt = stmt.where(Appointment.status == query["status"])
    if query["disease"]:
        stmt = stmt.where(Prediction.predicted_disease == query["disease"])
    if query["date_from"]:
        stmt = stmt.where(Appointment.scheduled_at >= datetime.combine(query["date_from"], time.min))
    if query["date_to"]:
        stmt = stmt.where(Appointment.scheduled_at < datetime.combine(query["date_to"] + timedelta(days=1), time.min))

    column = {
        "scheduled_at": Appointment.scheduled_at,
        "created_at": Appointment.created_at,
        "patient_name": func.lower(Patient.full_name),
        "confidence": Prediction.confidence,
    }[query["sort"]]
    ordered = column.asc() if query["order"] == "asc" else column.desc()
    stmt = stmt.order_by(ordered.nulls_last(), Appointment.id.desc())

    return db.paginate(stmt, page=query["page"], per_page=query["per_page"], error_out=False)


def update_appointment(appointment_id: int, changes: dict, user: User) -> Appointment:
    appointment = get_appointment(appointment_id)

    new_status = changes.get("status")
    if new_status and new_status != appointment.status:
        if new_status not in ROLE_STATUS_PERMISSIONS[user.role]:
            raise PermissionDenied(f"Your role cannot set status to '{new_status}'.")
        if new_status not in TRANSITIONS[appointment.status]:
            raise Conflict(
                f"Cannot change status from '{appointment.status}' to '{new_status}'.",
                code="INVALID_STATUS_TRANSITION",
            )

    schedule_changes = {k: v for k, v in changes.items() if k in ("scheduled_at", "appointment_type")}
    if schedule_changes and appointment.status != "pending":
        raise Conflict("Only pending appointments can be rescheduled.", code="APPOINTMENT_NOT_PENDING")

    old_status = appointment.status
    for field, value in changes.items():
        setattr(appointment, field, value)
    db.session.commit()
    logger.info(
        "appointment_updated",
        extra={
            "appointment_id": appointment.id,
            "fields": ",".join(sorted(changes)),
            "from_status": old_status,
            "to_status": appointment.status,
            "user_id": user.id,
        },
    )
    return appointment


def visit_history(appointment: Appointment, limit: int = 10) -> list[dict]:
    """Other appointments for the same patient (for the details page)."""
    stmt = (
        db.select(Appointment)
        .options(selectinload(Appointment.prediction))
        .where(Appointment.patient_id == appointment.patient_id, Appointment.id != appointment.id)
        .order_by(Appointment.scheduled_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": a.id,
            "scheduled_at": a.scheduled_at.isoformat(timespec="minutes"),
            "appointment_type": a.appointment_type,
            "status": a.status,
            "predicted_disease": a.prediction.predicted_disease if a.prediction else None,
        }
        for a in db.session.scalars(stmt)
    ]


def stats(today: date | None = None) -> dict:
    today = today or date.today()
    by_status = dict(
        db.session.execute(db.select(Appointment.status, func.count()).group_by(Appointment.status)).all()
    )
    start = datetime.combine(today, time.min)
    today_count = db.session.scalar(
        db.select(func.count())
        .select_from(Appointment)
        .where(Appointment.scheduled_at >= start, Appointment.scheduled_at < start + timedelta(days=1))
    )
    top_diseases = db.session.execute(
        db.select(Prediction.predicted_disease, func.count().label("n"))
        .where(Prediction.predicted_disease.is_not(None))
        .group_by(Prediction.predicted_disease)
        .order_by(func.count().desc(), Prediction.predicted_disease)
        .limit(5)
    ).all()

    return {
        "total_appointments": sum(by_status.values()),
        "by_status": {status: by_status.get(status, 0) for status in STATUSES},
        "scheduled_today": today_count,
        "total_patients": db.session.scalar(db.select(func.count()).select_from(Patient)),
        "top_predicted_diseases": [{"disease": d, "count": n} for d, n in top_diseases],
    }
