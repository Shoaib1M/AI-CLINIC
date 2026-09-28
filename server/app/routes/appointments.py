from flask import Blueprint, g, request

from ..auth import require_auth
from ..services import appointment_service
from ..utils.responses import json_body, ok
from ..utils.validators import (
    validate_appointment_create,
    validate_appointment_update,
    validate_list_query,
)

bp = Blueprint("appointments", __name__)


@bp.get("/appointments")
@require_auth("doctor", "frontdesk")
def list_appointments():
    query = validate_list_query(request.args)
    page = appointment_service.list_appointments(query)
    return ok(
        [a.to_dict() for a in page.items],
        meta={"page": page.page, "per_page": page.per_page, "total": page.total, "pages": page.pages},
    )


@bp.post("/appointments")
@require_auth("frontdesk")
def create_appointment():
    data = validate_appointment_create(json_body())
    appointment = appointment_service.create_appointment(data, g.current_user)
    return ok(appointment.to_dict(include_details=True), 201)


@bp.get("/appointments/stats")
@require_auth("doctor", "frontdesk")
def appointment_stats():
    return ok(appointment_service.stats())


@bp.get("/appointments/<int:appointment_id>")
@require_auth("doctor", "frontdesk")
def get_appointment(appointment_id: int):
    appointment = appointment_service.get_appointment(appointment_id)
    data = appointment.to_dict(include_details=True)
    data["visit_history"] = appointment_service.visit_history(appointment)
    return ok(data)


@bp.patch("/appointments/<int:appointment_id>")
@require_auth("doctor", "frontdesk")
def update_appointment(appointment_id: int):
    changes = validate_appointment_update(json_body())
    appointment = appointment_service.update_appointment(appointment_id, changes, g.current_user)
    return ok(appointment.to_dict(include_details=True))
