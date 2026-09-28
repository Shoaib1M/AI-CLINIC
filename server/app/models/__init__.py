"""MongoDB document shapes and their JSON serialisers.

There is no ORM: services read and write plain dicts with PyMongo, and these
modules define what each collection's documents look like and how they are
turned into API responses.
"""

from .appointment import APPOINTMENT_TYPES, STATUSES, appointment_to_dict
from .base import iso, utcnow
from .patient import patient_to_dict
from .prediction import PREDICTION_STATUSES, prediction_to_dict
from .prescription import prescription_to_dict
from .user import ROLES, User, user_to_dict

__all__ = [
    "APPOINTMENT_TYPES",
    "PREDICTION_STATUSES",
    "ROLES",
    "STATUSES",
    "User",
    "appointment_to_dict",
    "iso",
    "patient_to_dict",
    "prediction_to_dict",
    "prescription_to_dict",
    "user_to_dict",
    "utcnow",
]
