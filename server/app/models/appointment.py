from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, iso

APPOINTMENT_TYPES = ("regular_checkup", "follow_up", "consultation", "emergency")
STATUSES = ("pending", "completed", "cancelled")


class Appointment(TimestampMixin, db.Model):
    """A scheduled visit, with the symptoms captured at the front desk."""

    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    appointment_type: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Normalised symptom strings as entered, including ones the model does not know.
    symptoms: Mapped[list] = mapped_column(JSON, default=list)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    patient = relationship("Patient", back_populates="appointments")
    created_by = relationship("User")
    prediction = relationship(
        "Prediction", back_populates="appointment", uselist=False, cascade="all, delete-orphan"
    )
    prescriptions = relationship(
        "Prescription",
        back_populates="appointment",
        cascade="all, delete-orphan",
        order_by="Prescription.created_at.desc()",
    )

    def to_dict(self, *, include_details: bool = False) -> dict:
        data = {
            "id": self.id,
            "patient": self.patient.to_dict(),
            "scheduled_at": self.scheduled_at.isoformat(timespec="minutes"),
            "appointment_type": self.appointment_type,
            "status": self.status,
            "symptoms": list(self.symptoms or []),
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "prescription_count": len(self.prescriptions),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_details:
            data["created_by"] = self.created_by.to_dict() if self.created_by else None
            data["prescriptions"] = [p.to_dict() for p in self.prescriptions]
        return data
