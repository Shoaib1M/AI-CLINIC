from flask import Blueprint

from ..extensions import mongo
from ..services.prediction_service import get_predictor
from ..utils.responses import ok

bp = Blueprint("health", __name__)


@bp.get("/health")
def health():
    """Liveness/readiness probe. Public; exposes no data."""
    try:
        mongo.db.command("ping")
        database = "ok"
    except Exception:
        database = "unavailable"
    predictor = get_predictor(required=False)
    status = "ok" if database == "ok" and predictor else "degraded"
    return ok(
        {
            "status": status,
            "database": database,
            "model": {"loaded": predictor is not None, "version": predictor.version if predictor else None},
        },
        200 if database == "ok" else 503,
    )
