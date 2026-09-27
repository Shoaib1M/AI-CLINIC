"""SQLAlchemy models. Importing this package registers every table."""

from .appointment import APPOINTMENT_TYPES, STATUSES, Appointment
from .patient import Patient
from .prediction import Prediction
from .prescription import Prescription
from .user import ROLES, User

__all__ = [
    "APPOINTMENT_TYPES",
    "ROLES",
    "STATUSES",
    "Appointment",
    "Patient",
    "Prediction",
    "Prescription",
    "User",
]
