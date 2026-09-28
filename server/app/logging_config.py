"""Logging setup: human-readable text locally, one-JSON-object-per-line in production.

Log calls pass structured context through `extra={...}`; both formatters render
it. Patient names, phone numbers and symptoms are deliberately never logged.
"""

import json
import logging
import logging.config
from datetime import datetime, timezone

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}


def _extra_fields(record: logging.LogRecord) -> dict:
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
            **_extra_fields(record),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = _extra_fields(record)
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base


def configure_logging(level: str = "INFO", fmt: str = "text") -> None:
    formatter = "json" if fmt == "json" else "text"
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": JsonFormatter},
                "text": {
                    "()": TextFormatter,
                    "format": "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                },
            },
            "handlers": {
                "console": {"class": "logging.StreamHandler", "formatter": formatter},
            },
            "root": {"level": level.upper(), "handlers": ["console"]},
        }
    )
