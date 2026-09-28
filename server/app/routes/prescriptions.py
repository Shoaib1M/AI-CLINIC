import io

from flask import Blueprint, g, send_file

from ..auth import require_auth
from ..services import prescription_service
from ..utils.responses import json_body, ok
from ..utils.validators import validate_prescription

bp = Blueprint("prescriptions", __name__)


@bp.post("/prescriptions")
@require_auth("doctor")
def create_prescription():
    data = validate_prescription(json_body())
    return ok(prescription_service.create_prescription(data, g.current_user), 201)


@bp.get("/prescriptions/<int:prescription_id>")
@require_auth("doctor", "frontdesk")
def get_prescription(prescription_id: int):
    return ok(prescription_service.get_prescription(prescription_id))


@bp.get("/prescriptions/<int:prescription_id>/pdf")
@require_auth("doctor", "frontdesk")
def prescription_pdf(prescription_id: int):
    pdf, filename = prescription_service.render_pdf(prescription_id)
    return send_file(io.BytesIO(pdf), mimetype="application/pdf", as_attachment=True, download_name=filename)
