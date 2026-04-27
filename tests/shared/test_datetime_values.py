from datetime import datetime, timezone

from src.shared.datetime_values import (
    format_utc_iso_datetime,
    parse_taipei_display_datetime,
    parse_utc_iso_datetime,
    taipei_display_datetime_to_utc_iso,
    utc_iso_datetime_to_taipei_display,
)


def test_taipei_display_datetime_to_utc_iso_converts_to_storage_value() -> None:
    assert taipei_display_datetime_to_utc_iso("2024 / 04 / 28 15:32") == (
        "2024-04-28T07:32:00Z"
    )


def test_utc_iso_datetime_to_taipei_display_converts_to_ui_value() -> None:
    assert utc_iso_datetime_to_taipei_display("2024-04-28T07:32:00Z") == (
        "2024 / 04 / 28 15:32"
    )


def test_taipei_display_datetime_rejects_invalid_values() -> None:
    assert parse_taipei_display_datetime("2024 / 02 / 30 15:32") is None
    assert taipei_display_datetime_to_utc_iso("2024 / 04 / 28 25:32") is None


def test_utc_iso_datetime_rejects_non_utc_or_invalid_values() -> None:
    assert parse_utc_iso_datetime("2024-04-28T07:32:00+08:00") is None
    assert utc_iso_datetime_to_taipei_display("2024-04-28T07:61:00Z") is None


def test_format_utc_iso_datetime_normalizes_timezone_and_seconds() -> None:
    assert format_utc_iso_datetime(datetime(2024, 4, 28, 7, 32, 19, 123, tzinfo=timezone.utc)) == (
        "2024-04-28T07:32:19Z"
    )
