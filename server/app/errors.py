"""API error types and the handlers that turn them into consistent JSON.

Every error response has the shape:

    {"error": {"code": "INVALID_INPUT", "message": "...", "details": {...}}}
"""

import logging

from flask import jsonify
from pymongo.errors import ConnectionFailure
from werkzeug.exceptions import HTTPException

logger = logging.getLogger(__name__)


class APIError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, code: str | None = None, details=None):
        super().__init__(message or self.message)
        self.message = message or self.message
        if code:
            self.code = code
        self.details = details

    def to_dict(self) -> dict:
        body = {"code": self.code, "message": self.message}
        if self.details:
            body["details"] = self.details
        return {"error": body}


class ValidationError(APIError):
    status_code = 400
    code = "INVALID_INPUT"
    message = "The request contains invalid data."


class AuthenticationError(APIError):
    status_code = 401
    code = "UNAUTHENTICATED"
    message = "Authentication is required."


class PermissionDenied(APIError):
    status_code = 403
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class NotFound(APIError):
    status_code = 404
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class Conflict(APIError):
    status_code = 409
    code = "CONFLICT"
    message = "The request conflicts with the current state of the resource."


class UnprocessableInput(APIError):
    status_code = 422
    code = "UNPROCESSABLE"
    message = "The request was well-formed but could not be processed."


class ServiceUnavailable(APIError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "The service is temporarily unavailable."


_HTTP_CODES = {
    400: "BAD_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
}


def register_error_handlers(app) -> None:
    @app.errorhandler(APIError)
    def handle_api_error(error: APIError):
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        code = _HTTP_CODES.get(error.code, "HTTP_ERROR")
        return jsonify({"error": {"code": code, "message": error.description}}), error.code

    @app.errorhandler(ConnectionFailure)  # includes server-selection timeouts
    def handle_database_unavailable(error):
        logger.error("database_unavailable", extra={"reason": str(error)[:300]})
        body = ServiceUnavailable("The database is unreachable. Please try again shortly.", code="DATABASE_UNAVAILABLE")
        return jsonify(body.to_dict()), 503

    @app.errorhandler(Exception)
    def handle_unexpected(error: Exception):
        # Never leak internals (stack traces, queries, file paths) to clients.
        logger.exception("unhandled_exception")
        return jsonify(APIError().to_dict()), 500
