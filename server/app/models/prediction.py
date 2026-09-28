from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, iso

PREDICTION_STATUSES = ("ok", "no_known_symptoms", "model_unavailable")


class Prediction(TimestampMixin, db.Model):
    """The AI decision-support output recorded when an appointment was created.

    Kept in its own table, separate from anything a clinician authors, and
    stamped with the model version so every suggestion is traceable.
    """

    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30))
    predicted_disease: Mapped[str | None] = mapped_column(String(100), index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[str | None] = mapped_column(String(20))
    top_predictions: Mapped[list] = mapped_column(JSON, default=list)
    recognized_symptoms: Mapped[list] = mapped_column(JSON, default=list)
    unknown_symptoms: Mapped[list] = mapped_column(JSON, default=list)
    reference_treatments: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    model_version: Mapped[str | None] = mapped_column(String(80))

    appointment = relationship("Appointment", back_populates="prediction")

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "predicted_disease": self.predicted_disease,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level,
            "top_predictions": self.top_predictions or [],
            "recognized_symptoms": self.recognized_symptoms or [],
            "unknown_symptoms": self.unknown_symptoms or [],
            "reference_treatments": self.reference_treatments or [],
            "warnings": self.warnings or [],
            "model_version": self.model_version,
            "created_at": iso(self.created_at),
        }
