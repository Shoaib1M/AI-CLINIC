"""Model lifecycle and prediction use-cases.

The model is loaded exactly once, when the app starts, and kept on
`app.extensions["predictor"]`. If artifacts are missing or invalid the API
still starts: appointments can be booked, predictions are recorded as
"model_unavailable", and /api/predictions returns 503. It never retrains.
"""

import logging

from flask import current_app

from ..errors import ServiceUnavailable, UnprocessableInput
from ..ml import DiseasePredictor, ModelArtifactError, NoKnownSymptomsError
from ..ml.preprocessing import SYMPTOM_ALIASES
from ..models import Prediction

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Educational decision-support output from a model trained on a small synthetic "
    "dataset. It is not a diagnosis and has not been clinically validated. "
    "'confidence' is the share of decision-tree votes, not the probability of disease."
)


def init_app(app) -> None:
    model_dir = app.config["MODEL_DIR"]
    try:
        predictor = DiseasePredictor.from_directory(model_dir)
    except ModelArtifactError as exc:
        app.extensions["predictor"] = None
        logger.error("model_load_failed", extra={"model_dir": str(model_dir), "reason": str(exc)})
        return
    app.extensions["predictor"] = predictor
    logger.info(
        "model_loaded",
        extra={
            "model_version": predictor.version,
            "classes": len(predictor.classes),
            "features": len(predictor.known_symptoms),
        },
    )


def get_predictor(required: bool = True) -> DiseasePredictor | None:
    predictor = current_app.extensions.get("predictor")
    if predictor is None and required:
        raise ServiceUnavailable(
            "The prediction model is not loaded. Train it with `python -m scripts.train_model`.",
            code="MODEL_UNAVAILABLE",
        )
    return predictor


def predict(symptoms: list[str], top_k: int = 3) -> dict:
    predictor = get_predictor()
    try:
        result = predictor.predict(symptoms, top_k=top_k)
    except NoKnownSymptomsError as exc:
        logger.info("prediction_rejected", extra={"reason": "no_known_symptoms", "n_symptoms": len(symptoms)})
        raise UnprocessableInput(
            "None of the symptoms are recognised by the model. Choose symptoms from the suggestions.",
            code="NO_KNOWN_SYMPTOMS",
            details={"unknown_symptoms": exc.unknown},
        ) from exc

    logger.info(
        "prediction_made",
        extra={
            "prediction": result.prediction,
            "confidence": result.confidence,
            "n_recognized": len(result.recognized_symptoms),
            "n_unknown": len(result.unknown_symptoms),
        },
    )
    return {**result.to_dict(), "disclaimer": DISCLAIMER}


def prediction_record_for(symptoms: list[str]) -> Prediction:
    """Build the Prediction row stored with a new appointment. Never raises for
    model problems: booking an appointment must not depend on the model."""
    predictor = get_predictor(required=False)
    if predictor is None:
        return Prediction(status="model_unavailable", unknown_symptoms=[], warnings=[])

    try:
        result = predictor.predict(symptoms)
    except NoKnownSymptomsError as exc:
        return Prediction(
            status="no_known_symptoms",
            unknown_symptoms=exc.unknown,
            model_version=predictor.version,
            warnings=["None of the symptoms are recognised by the model, so no suggestion was made."],
        )
    except Exception:  # defensive: log and continue booking
        logger.exception("prediction_failed")
        return Prediction(status="model_unavailable", warnings=["The model failed on this input."])

    logger.info("prediction_made", extra={"prediction": result.prediction, "confidence": result.confidence})
    return Prediction(
        status="ok",
        predicted_disease=result.prediction,
        confidence=result.confidence,
        confidence_level=result.confidence_level,
        top_predictions=[{"disease": r.disease, "probability": r.probability} for r in result.top_predictions],
        recognized_symptoms=result.recognized_symptoms,
        unknown_symptoms=result.unknown_symptoms,
        reference_treatments=result.reference_treatments,
        warnings=result.warnings,
        model_version=result.model_version,
    )


def model_info() -> dict:
    predictor = get_predictor(required=False)
    if predictor is None:
        return {"loaded": False, "disclaimer": DISCLAIMER}
    meta = predictor.metadata
    return {
        "loaded": True,
        "model_version": predictor.version,
        "algorithm": meta.get("algorithm"),
        "hyperparameters": meta.get("hyperparameters"),
        "trained_at": meta.get("trained_at"),
        "sklearn_version": meta.get("sklearn_version"),
        "classes": predictor.classes,
        "symptoms": predictor.known_symptoms,
        "symptom_aliases": SYMPTOM_ALIASES,
        "dataset": meta.get("dataset"),
        "evaluation": meta.get("evaluation"),
        "disclaimer": DISCLAIMER,
    }
