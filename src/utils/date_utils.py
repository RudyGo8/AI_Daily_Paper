from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def parse_target_date(date_text: str | None) -> date:
    if not date_text:
        return datetime.now().date()
    return datetime.strptime(date_text, "%Y-%m-%d").date()


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    raw = value.strip()
    if not raw:
        return datetime.now(timezone.utc)

    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        pass

    patterns = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]
    for pattern in patterns:
        try:
            parsed = datetime.strptime(raw, pattern)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            continue

    return datetime.now(timezone.utc)


def get_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def to_local_date(dt: datetime, timezone_name: str) -> date:
    return dt.astimezone(get_timezone(timezone_name)).date()


def is_same_day(dt: datetime, target: date, timezone_name: str = "UTC") -> bool:
    return to_local_date(dt, timezone_name) == target
