"""Doctor-authored prescriptions and their PDF export."""

import logging

from flask import current_app
from sqlalchemy.orm import selectinload

from ..errors import APIError, Conflict, NotFound
from ..extensions import db
from ..models import Appointment, Prescription, User
from . import appointment_service
from .pdf_service import build_prescription_pdf

logger = logging.getLogger(__name__)


def create_prescription(data: dict, doctor: User) -> Prescription:
    appointment = appointment_service.get_appointment(data["appointment_id"])
    if appointment.status == "cancelled":
        raise Conflict("Cannot write a prescription for a cancelled appointment.", code="APPOINTMENT_CANCELLED")

    prescription = Prescription(
        appointment=appointment,
        doctor=doctor,  # always the signed-in doctor, never a name from the request body
        diagnosis=data["diagnosis"],
        medications=data["medications"],
        notes=data["notes"],
    )
    db.session.add(prescription)
    db.session.commit()
    logger.info(
        "prescription_created",
        extra={"prescription_id": prescription.id, "appointment_id": appointment.id, "doctor_id": doctor.id},
    )
    return prescription


def get_prescription(prescription_id: int) -> Prescription:
    prescription = db.session.scalar(
        db.select(Prescription)
        .options(
            selectinload(Prescription.doctor),
            selectinload(Prescription.appointment).selectinload(Appointment.patient),
            selectinload(Prescription.appointment).selectinload(Appointment.prediction),
        )
        .where(Prescription.id == prescription_id)
    )
    if prescription is None:
        raise NotFound("Prescription not found.", code="PRESCRIPTION_NOT_FOUND")
    return prescription


def render_pdf(prescription: Prescription) -> tuple[bytes, str]:
    """Return (pdf_bytes, filename). The filename contains no patient data."""
    try:
        pdf = build_prescription_pdf(
            prescription,
            clinic_name=current_app.config["CLINIC_NAME"],
            clinic_address=current_app.config["CLINIC_ADDRESS"],
        )
    except Exception as exc:
        logger.exception("pdf_generation_failed", extra={"prescription_id": prescription.id})
        raise APIError("Failed to generate the PDF.", code="PDF_GENERATION_FAILED") from exc
    logger.info("pdf_generated", extra={"prescription_id": prescription.id, "bytes": len(pdf)})
    return pdf, f"prescription_RX-{prescription.id:06d}.pdf"
