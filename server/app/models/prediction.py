"""The AI suggestion stored *inside* each appointment document (`appointment.prediction`).

It is written once when the appointment is created and never edited, is
always read together with its appointment, and is stamped with the model
version, so embedding it is the natural MongoDB shape (no join, atomic write).
"""

from .base import iso

PREDICTION_STATUSES = ("ok", "no_known_symptoms", "model_unavailable")


def prediction_to_dict(doc: dict | None) -> dict | None:
    if not doc:
        return None
    return {
        "status": doc["status"],
        "predicted_disease": doc.get("predicted_disease"),
        "confidence": doc.get("confidence"),
        "confidence_level": doc.get("confidence_level"),
        "top_predictions": doc.get("top_predictions") or [],
        "recognized_symptoms": doc.get("recognized_symptoms") or [],
        "unknown_symptoms": doc.get("unknown_symptoms") or [],
        "reference_treatments": doc.get("reference_treatments") or [],
        "warnings": doc.get("warnings") or [],
        "model_version": doc.get("model_version"),
        "created_at": iso(doc.get("created_at")),
    }
