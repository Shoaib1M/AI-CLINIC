"""JWT authentication and role-based access control.

Flow:
    POST /api/auth/login  -> verify password hash -> sign a JWT (HS256)
    client stores token   -> sends `Authorization: Bearer <token>`
    @require_auth(...)    -> verify signature + expiry -> load user -> check role
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request
from werkzeug.security import generate_password_hash

from .errors import AuthenticationError, PermissionDenied
from .extensions import db
from .models import User

logger = logging.getLogger(__name__)

# Compared against when the username does not exist, so a failed login takes
# the same time whether or not the account exists (no username enumeration).
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def authenticate(username: str, password: str) -> User:
    user = db.session.scalar(db.select(User).filter_by(username=username))
    if user is None:
        User(password_hash=_DUMMY_HASH).check_password(password)
        raise AuthenticationError("Invalid username or password.", code="INVALID_CREDENTIALS")
    if not user.check_password(password) or not user.is_active:
        raise AuthenticationError("Invalid username or password.", code="INVALID_CREDENTIALS")
    return user


def issue_token(user: User) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=current_app.config["JWT_EXPIRES_MINUTES"])
    claims = {"sub": str(user.id), "role": user.role, "iat": now, "exp": expires}
    token = jwt.encode(claims, current_app.config["JWT_SECRET"], algorithm=current_app.config["JWT_ALGORITHM"])
    return token, expires


def _user_from_request() -> User:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError()
    try:
        claims = jwt.decode(
            token,
            current_app.config["JWT_SECRET"],
            algorithms=[current_app.config["JWT_ALGORITHM"]],  # pin: never accept "none"
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Your session has expired. Please sign in again.", code="TOKEN_EXPIRED") from exc
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError("Invalid authentication token.", code="INVALID_TOKEN") from exc

    user = db.session.get(User, int(claims["sub"])) if claims["sub"].isdigit() else None
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid authentication token.", code="INVALID_TOKEN")
    return user


def require_auth(*roles: str):
    """Decorator: require a valid token, and optionally one of `roles`.

    The role is read from the database, not the token, so a role change or
    deactivation takes effect immediately.
    """

    def decorator(view):
        @wraps(view)
        def wrapper(*args, **kwargs):
            user = _user_from_request()
            if roles and user.role not in roles:
                raise PermissionDenied()
            g.current_user = user
            return view(*args, **kwargs)

        return wrapper

    return decorator
