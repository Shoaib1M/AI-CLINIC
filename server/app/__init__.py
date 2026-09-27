"""AI-CLINIC REST API — application factory."""

import logging
from pathlib import Path

from flask import Flask

from . import cli
from .config import finalize_secrets, get_config
from .errors import register_error_handlers
from .extensions import cors, db
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
    _ensure_sqlite_directory(app.config["SQLALCHEMY_DATABASE_URI"])

    db.init_app(app)
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

    with app.app_context():
        # SQLite + create_all keeps setup to zero steps. A production system
        # would manage schema changes with migrations (Alembic).
        db.create_all()

    # Load the ML model once per process. Training is a separate offline step.
    prediction_service.init_app(app)

    logger.info("app_started", extra={"env": app.config["APP_ENV"]})
    return app


def _ensure_sqlite_directory(uri: str) -> None:
    prefix = "sqlite:///"
    if uri.startswith(prefix) and ":memory:" not in uri:
        Path(uri[len(prefix):]).parent.mkdir(parents=True, exist_ok=True)
