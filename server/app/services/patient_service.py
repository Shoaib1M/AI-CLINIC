"""Patient lookup and creation."""

import logging

from sqlalchemy import func, or_

from ..errors import NotFound
from ..extensions import db
from ..models import Appointment, Patient

logger = logging.getLogger(__name__)


def get_patient(patient_id: int) -> Patient:
    patient = db.session.get(Patient, patient_id)
    if patient is None:
        raise NotFound("Patient not found.", code="PATIENT_NOT_FOUND")
    return patient


def find_or_create_patient(full_name: str, phone: str) -> Patient:
    """Reuse an existing record with the same name and phone, else create one."""
    patient = db.session.scalar(
        db.select(Patient).where(func.lower(Patient.full_name) == full_name.lower(), Patient.phone == phone)
    )
    if patient is None:
        patient = Patient(full_name=full_name, phone=phone)
        db.session.add(patient)
        db.session.flush()  # assign an id
        logger.info("patient_created", extra={"patient_id": patient.id})
    return patient


def search_patients(query: str, limit: int = 10) -> list[dict]:
    """Case-insensitive match on name or phone, most recently seen first."""
    needle = query.strip().lower()
    if not needle:
        return []
    last_visit = func.max(Appointment.scheduled_at).label("last_visit")
    visits = func.count(Appointment.id).label("visits")
    stmt = (
        db.select(Patient, last_visit, visits)
        .outerjoin(Appointment)
        .where(
            or_(
                func.lower(Patient.full_name).contains(needle, autoescape=True),
                Patient.phone.contains(needle, autoescape=True),
            )
        )
        .group_by(Patient.id)
        .order_by(last_visit.desc().nulls_last(), Patient.full_name)
        .limit(limit)
    )
    return [
        {
            **patient.to_dict(),
            "last_visit": last.isoformat(timespec="minutes") if last else None,
            "visit_count": count,
        }
        for patient, last, count in db.session.execute(stmt)
    ]
