"""Application configuration, read from environment variables.

Every setting has a development-friendly default so the project runs after a
plain clone. Production refuses to start without a real JWT secret.
"""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

SERVER_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVER_DIR.parent

# `.env` lives at the repository root (see .env.example). Real environment
# variables always win over values in the file.
load_dotenv(REPO_ROOT / ".env", override=False)


def _resolve_path(value: str | None, default: Path) -> Path:
    """Resolve a path from the environment relative to the repository root."""
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class BaseConfig:
    APP_ENV = "development"
    DEBUG = False
    TESTING = False

    # `or` (not a getenv default) so an empty value copied from .env.example
    # falls back to the default instead of becoming an empty URL.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or f"sqlite:///{SERVER_DIR / 'instance' / 'ai_clinic.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES") or 480)

    MODEL_DIR = _resolve_path(os.getenv("MODEL_DIR"), REPO_ROOT / "models")
    DATASET_PATH = _resolve_path(
        os.getenv("DATASET_PATH"), REPO_ROOT / "data" / "updated_synthetic_medical_dataset.csv"
    )

    CORS_ORIGINS = _split_csv(os.getenv("CORS_ORIGINS") or "http://localhost:5173")

    CLINIC_NAME = os.getenv("CLINIC_NAME") or "AI-CLINIC Demo Clinic"
    CLINIC_ADDRESS = os.getenv("CLINIC_ADDRESS") or "For demonstration purposes only"

    LOG_LEVEL = os.getenv("LOG_LEVEL") or "INFO"
    LOG_FORMAT = os.getenv("LOG_FORMAT") or "text"  # "text" or "json"

    # Reject oversized request bodies early (the API only accepts small JSON).
    MAX_CONTENT_LENGTH = 64 * 1024


class DevelopmentConfig(BaseConfig):
    APP_ENV = "development"
    DEBUG = True


class TestingConfig(BaseConfig):
    APP_ENV = "testing"
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_SECRET = "test-secret-key-that-is-long-enough-for-hs256"
    LOG_LEVEL = "WARNING"


class ProductionConfig(BaseConfig):
    APP_ENV = "production"


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None) -> type[BaseConfig]:
    name = name or os.getenv("APP_ENV") or "development"
    try:
        return CONFIGS[name]
    except KeyError as exc:
        raise RuntimeError(f"Unknown APP_ENV '{name}'. Use one of: {', '.join(CONFIGS)}") from exc


def finalize_secrets(app) -> None:
    """Make sure a usable JWT secret exists before the app serves requests."""
    secret = app.config.get("JWT_SECRET", "")
    if len(secret) >= 32:
        return
    if app.config["APP_ENV"] == "production":
        raise RuntimeError("JWT_SECRET must be set to at least 32 characters in production.")
    # Development convenience: an ephemeral secret. Tokens stop working after a
    # restart, which is acceptable locally and impossible to leak via git.
    app.config["JWT_SECRET"] = secrets.token_urlsafe(48)
    app.logger.warning(
        "JWT_SECRET not set (or shorter than 32 chars); using an ephemeral secret. "
        "Set it in .env to keep sessions across restarts."
    )
