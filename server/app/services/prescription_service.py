"""Doctor-authored prescriptions and their PDF export."""

import logging

from flask import current_app

from ..errors import APIError, Conflict, NotFound
from ..extensions import mongo, next_id
from ..models import User, prescription_to_dict, utcnow
from . import appointment_service, patient_service
from .pdf_service import build_prescription_pdf

logger = logging.getLogger(__name__)


def create_prescription(data: dict, doctor: User) -> dict:
    appointment = appointment_service.get_appointment_doc(data["appointment_id"])
    if appointment["status"] == "cancelled":
        raise Conflict("Cannot write a prescription for a cancelled appointment.", code="APPOINTMENT_CANCELLED")

    now = utcnow()
    prescription = {
        "_id": next_id("prescriptions"),
        "appointment_id": appointment["_id"],
        "doctor_id": doctor.id,  # always the signed-in doctor, never a name from the request body
        "diagnosis": data["diagnosis"],
        "medications": data["medications"],
        "notes": data["notes"],
        "created_at": now,
        "updated_at": now,
    }
    mongo.db.prescriptions.insert_one(prescription)
    mongo.db.appointments.update_one({"_id": appointment["_id"]}, {"$inc": {"prescription_count": 1}})
    logger.info(
        "prescription_created",
        extra={"prescription_id": prescription["_id"], "appointment_id": appointment["_id"], "doctor_id": doctor.id},
    )
    return prescription_to_dict(prescription, mongo.db.users.find_one({"_id": doctor.id}))


def get_prescription_doc(prescription_id: int) -> dict:
    prescription = mongo.db.prescriptions.find_one({"_id": prescription_id})
    if prescription is None:
        raise NotFound("Prescription not found.", code="PRESCRIPTION_NOT_FOUND")
    return prescription


def get_prescription(prescription_id: int) -> dict:
    prescription = get_prescription_doc(prescription_id)
    return prescription_to_dict(prescription, mongo.db.users.find_one({"_id": prescription["doctor_id"]}))


def render_pdf(prescription_id: int) -> tuple[bytes, str]:
    """Return (pdf_bytes, filename). The filename contains no patient data."""
    prescription = get_prescription_doc(prescription_id)
    appointment = appointment_service.get_appointment_doc(prescription["appointment_id"])
    patient = patient_service.get_patient(appointment["patient_id"])
    doctor = mongo.db.users.find_one({"_id": prescription["doctor_id"]})
    try:
        pdf = build_prescription_pdf(
            prescription,
            appointment,
            patient,
            doctor,
            clinic_name=current_app.config["CLINIC_NAME"],
            clinic_address=current_app.config["CLINIC_ADDRESS"],
        )
    except Exception as exc:
        logger.exception("pdf_generation_failed", extra={"prescription_id": prescription_id})
        raise APIError("Failed to generate the PDF.", code="PDF_GENERATION_FAILED") from exc
    logger.info("pdf_generated", extra={"prescription_id": prescription_id, "bytes": len(pdf)})
    return pdf, f"prescription_RX-{prescription_id:06d}.pdf"
