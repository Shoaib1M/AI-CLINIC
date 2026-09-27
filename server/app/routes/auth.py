import logging

from flask import Blueprint, g

from ..auth import authenticate, issue_token, require_auth
from ..errors import AuthenticationError
from ..utils.responses import json_body, ok
from ..utils.validators import validate_login

bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


@bp.post("/auth/login")
def login():
    credentials = validate_login(json_body())
    try:
        user = authenticate(credentials["username"], credentials["password"])
    except AuthenticationError:
        logger.warning("login_failed")
        raise
    token, expires = issue_token(user)
    logger.info("login_succeeded", extra={"user_id": user.id, "role": user.role})
    return ok({"token": token, "expires_at": expires.isoformat(timespec="seconds"), "user": user.to_dict()})


@bp.get("/auth/me")
@require_auth()
def me():
    return ok(g.current_user.to_dict())
