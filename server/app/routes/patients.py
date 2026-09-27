from flask import Blueprint, request

from ..auth import require_auth
from ..services import patient_service
from ..utils.responses import ok

bp = Blueprint("patients", __name__)


@bp.get("/patients")
@require_auth("doctor", "frontdesk")
def search_patients():
    """Typeahead search by name or phone (max 10 results)."""
    query = (request.args.get("q") or "").strip()[:100]
    if len(query) < 2:
        return ok([])
    return ok(patient_service.search_patients(query))
