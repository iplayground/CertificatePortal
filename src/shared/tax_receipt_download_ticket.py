from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time


TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS = 600
TAX_RECEIPT_DOWNLOAD_TICKET_SCOPE = "taxReceiptDownload"


def build_tax_receipt_download_ticket(
    *,
    event_id: str,
    receipt_ids: list[str],
) -> str:
    payload = {
        "eventId": event_id,
        "exp": int(time.time()) + TAX_RECEIPT_DOWNLOAD_TICKET_MAX_AGE_SECONDS,
        "receiptIds": receipt_ids,
        "scope": TAX_RECEIPT_DOWNLOAD_TICKET_SCOPE,
    }
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = hmac.new(
        _get_tax_receipt_download_ticket_secret().encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def is_valid_tax_receipt_download_ticket(
    *,
    ticket: str,
    event_id: str,
    receipt_ids: list[str],
) -> bool:
    try:
        encoded_payload, encoded_signature = ticket.split(".", maxsplit=1)
    except ValueError:
        return False

    expected_signature = hmac.new(
        _get_tax_receipt_download_ticket_secret().encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _base64url_decode(encoded_signature)
    if actual_signature is None or not hmac.compare_digest(actual_signature, expected_signature):
        return False

    payload_bytes = _base64url_decode(encoded_payload)
    if payload_bytes is None:
        return False

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    expires_at = payload.get("exp")
    allowed_receipt_ids = payload.get("receiptIds")
    if (
        not isinstance(expires_at, int)
        or expires_at < int(time.time())
        or not isinstance(allowed_receipt_ids, list)
    ):
        return False

    return (
        payload.get("scope") == TAX_RECEIPT_DOWNLOAD_TICKET_SCOPE
        and payload.get("eventId") == event_id
        and bool(receipt_ids)
        and all(receipt_id in allowed_receipt_ids for receipt_id in receipt_ids)
    )


def _get_tax_receipt_download_ticket_secret() -> str:
    configured_secret = os.getenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "").strip()
    if configured_secret:
        return configured_secret

    csrf_secret = os.getenv("PORTAL_CSRF_SECRET", "").strip()
    if csrf_secret:
        return csrf_secret

    google_client_secret = os.getenv("PORTAL_GOOGLE_CLIENT_SECRET", "").strip()
    if google_client_secret:
        return google_client_secret

    if os.getenv("PORTAL_AUTH_BYPASS_ENABLED", "").strip().lower() == "true":
        return "local-dev-portal-csrf-secret"

    return ""


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes | None:
    try:
        padding = "=" * (-len(value) % 4)
        return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))
    except (ValueError, binascii.Error):
        return None
