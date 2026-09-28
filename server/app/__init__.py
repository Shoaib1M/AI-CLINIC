"""AI-CLINIC REST API — application factory."""

import logging

from flask import Flask
from pymongo.errors import PyMongoError

from . import cli
from .config import finalize_secrets, get_config, require_database_uri
from .errors import register_error_handlers
from .extensions import cors, ensure_indexes, mongo
from .logging_config import configure_logging
from .routes import register_blueprints
from .services import prediction_service

logger = logging.getLogger(__name__)


def create_app(config_name: str | None = None, overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))
    if overrides:
        app.config.update(overrides)

    configure_logging(app.config["LOG_LEVEL"], app.config["LOG_FORMAT"])
    finalize_secrets(app)
    require_database_uri(app)

    mongo.init_app(app)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        expose_headers=["Content-Disposition"],
    )
    register_error_handlers(app)
    register_blueprints(app)
    cli.register(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        # API responses contain patient data: never cache them.
        response.headers.setdefault("Cache-Control", "no-store")
        return response

    # MongoDB creates collections on first write; indexes are the only schema
    # to set up. If the cluster is unreachable the API still starts, reports
    # "database: unavailable" on /api/health and answers data requests with 503.
    try:
        ensure_indexes(app.extensions["mongo_db"])
        logger.info("database_connected", extra={"database": app.config["MONGODB_DB"]})
    except PyMongoError as exc:
        logger.error(
            "database_unreachable",
            extra={"reason": str(exc)[:300], "hint": "check MONGODB_URI and Atlas Network Access (IP allowlist)"},
        )

    # Load the ML model once per process. Training is a separate offline step.
    prediction_service.init_app(app)

    logger.info("app_started", extra={"env": app.config["APP_ENV"]})
    return app

