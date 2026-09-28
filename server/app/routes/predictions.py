from flask import Blueprint

from ..auth import require_auth
from ..services import prediction_service
from ..utils.responses import json_body, ok
from ..utils.validators import validate_prediction_request

bp = Blueprint("predictions", __name__)


@bp.post("/predictions")
@require_auth("doctor", "frontdesk")
def predict():
    """Stateless prediction: nothing is stored. Used for previews."""
    data = validate_prediction_request(json_body())
    return ok(prediction_service.predict(data["symptoms"], data["top_k"]))


@bp.get("/model")
def model_info():
    """Public model card: version, vocabulary, classes and evaluation metrics."""
    return ok(prediction_service.model_info())
