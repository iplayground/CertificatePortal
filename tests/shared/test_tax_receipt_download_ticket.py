from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from src.shared import tax_receipt_download_ticket
from src.shared.tax_receipt_download_ticket import (
    TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS,
    build_tax_receipt_download_ticket,
    read_tax_receipt_download_ticket_payload,
)


def _decode_ticket_payload(ticket: str) -> dict[str, object]:
    parts = ticket.split(".", maxsplit=1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise ValueError("Invalid ticket format: expected '<payload>.<signature>'")

    encoded_payload = parts[0]
    padding = "=" * (-len(encoded_payload) % 4)
    return json.loads(base64.urlsafe_b64decode(f"{encoded_payload}{padding}"))


def _encode_ticket_payload(payload: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")


def _sign_ticket_payload(encoded_payload: str, secret: str) -> str:
    signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")


def _with_signed_ticket_payload(
    *,
    payload: dict[str, object],
    secret: str = "ticket-secret",
) -> str:
    encoded_payload = _encode_ticket_payload(payload)
    return f"{encoded_payload}.{_sign_ticket_payload(encoded_payload, secret)}"


def test_build_tax_receipt_download_ticket_uses_configured_max_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked_now = 1000.2
    max_age_seconds = 1200

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setenv(
        "TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS",
        str(max_age_seconds),
    )
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: mocked_now)

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    assert _decode_ticket_payload(ticket)["exp"] == int(mocked_now) + max_age_seconds


@pytest.mark.parametrize("configured_max_age", ["invalid", "0", "-60"])
def test_build_tax_receipt_download_ticket_falls_back_to_default_max_age(
    monkeypatch: pytest.MonkeyPatch,
    configured_max_age: str,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS", configured_max_age)
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: 1000.2)

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    assert (
        _decode_ticket_payload(ticket)["exp"]
        == 1000 + TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS
    )


def test_build_tax_receipt_download_ticket_accepts_large_positive_max_age(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked_now = 1000.2
    max_age_seconds = 86400

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setenv(
        "TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS",
        str(max_age_seconds),
    )
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: mocked_now)

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    assert _decode_ticket_payload(ticket)["exp"] == int(mocked_now) + max_age_seconds


def test_tax_receipt_download_ticket_prefers_dedicated_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setenv("PORTAL_CSRF_SECRET", "csrf-fallback-secret")

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "csrf-fallback-secret")
    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )


def test_tax_receipt_download_ticket_uses_portal_csrf_secret_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", raising=False)
    monkeypatch.setenv("PORTAL_CSRF_SECRET", "csrf-fallback-secret")
    monkeypatch.delenv("PORTAL_AUTH_BYPASS_ENABLED", raising=False)
    monkeypatch.delenv("PORTAL_GOOGLE_CLIENT_SECRET", raising=False)

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "csrf-fallback-secret")
    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is not None
    )


def test_tax_receipt_download_ticket_uses_local_bypass_secret_as_last_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", raising=False)
    monkeypatch.delenv("PORTAL_CSRF_SECRET", raising=False)
    monkeypatch.delenv("PORTAL_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("PORTAL_AUTH_BYPASS_ENABLED", "true")

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "local-dev-portal-csrf-secret")
    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is not None
    )


def test_google_client_secret_is_not_used_for_tax_receipt_download_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", raising=False)
    monkeypatch.delenv("PORTAL_CSRF_SECRET", raising=False)
    monkeypatch.delenv("PORTAL_AUTH_BYPASS_ENABLED", raising=False)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "google-client-secret")

    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "google-client-secret")
    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )


def test_read_tax_receipt_download_ticket_rejects_mismatched_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    valid_ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )
    encoded_payload, _ = valid_ticket.split(".", maxsplit=1)
    tampered_ticket = f"{encoded_payload}.{_sign_ticket_payload(encoded_payload, 'wrong-secret')}"

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=tampered_ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )


def test_read_tax_receipt_download_ticket_rejects_mismatched_event_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_other",
            receipt_ids=["trec_1"],
        )
        is None
    )


def test_read_tax_receipt_download_ticket_rejects_mismatched_receipt_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_2"],
        )
        is None
    )


def test_read_tax_receipt_download_ticket_rejects_payload_with_invalid_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: 1000.2)
    ticket = _with_signed_ticket_payload(
        payload={
            "eventId": "evt_tax",
            "exp": 2000,
            "receiptIds": ["trec_1"],
            "scope": "otherScope",
        }
    )

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )


def test_read_tax_receipt_download_ticket_rejects_expired_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocked_now = 1000.2
    expired_at = 999

    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: mocked_now)
    ticket = _with_signed_ticket_payload(
        payload={
            "eventId": "evt_tax",
            "exp": expired_at,
            "receiptIds": ["trec_1"],
            "scope": "taxReceiptDownload",
        }
    )

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"exp": 2000, "receiptIds": ["trec_1"], "scope": "taxReceiptDownload"},
        {"eventId": "evt_tax", "receiptIds": ["trec_1"], "scope": "taxReceiptDownload"},
        {"eventId": "evt_tax", "exp": 2000, "scope": "taxReceiptDownload"},
    ],
)
def test_read_tax_receipt_download_ticket_rejects_missing_required_fields(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "ticket-secret")
    monkeypatch.setattr(tax_receipt_download_ticket.time, "time", lambda: 1000.2)
    ticket = _with_signed_ticket_payload(payload=payload)

    assert (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id="evt_tax",
            receipt_ids=["trec_1"],
        )
        is None
    )
