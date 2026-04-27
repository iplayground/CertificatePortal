from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


TAIPEI_TZ = ZoneInfo("Asia/Taipei")
DISPLAY_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{4}) / (?P<month>\d{2}) / (?P<day>\d{2}) "
    r"(?P<hour>\d{2}):(?P<minute>\d{2})$"
)
UTC_ISO_DATETIME_PATTERN = re.compile(
    r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})T"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})Z$"
)


def format_utc_iso_datetime(value: datetime) -> str:
    utc_value = value.astimezone(timezone.utc).replace(microsecond=0)
    return utc_value.isoformat().replace("+00:00", "Z")


def parse_taipei_display_datetime(value: str) -> datetime | None:
    match = DISPLAY_DATETIME_PATTERN.fullmatch(value.strip())
    if not match:
        return None

    try:
        return datetime(
            int(match["year"]),
            int(match["month"]),
            int(match["day"]),
            int(match["hour"]),
            int(match["minute"]),
            tzinfo=TAIPEI_TZ,
        )
    except ValueError:
        return None


def taipei_display_datetime_to_utc_iso(value: str) -> str | None:
    parsed_value = parse_taipei_display_datetime(value)
    if parsed_value is None:
        return None

    return format_utc_iso_datetime(parsed_value)


def parse_utc_iso_datetime(value: str) -> datetime | None:
    match = UTC_ISO_DATETIME_PATTERN.fullmatch(value.strip())
    if not match:
        return None

    try:
        return datetime(
            int(match["year"]),
            int(match["month"]),
            int(match["day"]),
            int(match["hour"]),
            int(match["minute"]),
            int(match["second"]),
            tzinfo=timezone.utc,
        )
    except ValueError:
        return None


def utc_iso_datetime_to_taipei_display(value: str) -> str | None:
    parsed_value = parse_utc_iso_datetime(value)
    if parsed_value is None:
        return None

    taipei_value = parsed_value.astimezone(TAIPEI_TZ)
    return taipei_value.strftime("%Y / %m / %d %H:%M")
