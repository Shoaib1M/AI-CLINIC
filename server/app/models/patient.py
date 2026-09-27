from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, iso


class Patient(TimestampMixin, db.Model):
    """A person who visits the clinic. One patient has many appointments.

    Phone is indexed but not unique: family members often share a number.
    """

    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), index=True)
    phone: Mapped[str] = mapped_column(String(20), index=True)

    appointments = relationship(
        "Appointment", back_populates="patient", order_by="Appointment.scheduled_at.desc()"
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "phone": self.phone,
            "created_at": iso(self.created_at),
        }
