from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC, millisecond precision (what MongoDB stores and returns)."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return now.replace(microsecond=now.microsecond // 1000 * 1000)


def iso(value: datetime | None) -> str | None:
    """Serialise a naive-UTC timestamp as ISO 8601 with an explicit Z."""
    return value.isoformat(timespec="seconds") + "Z" if value else None
