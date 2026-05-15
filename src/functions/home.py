from __future__ import annotations

import logging
import os
import tempfile
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
from datetime import datetime, timezone
from functools import lru_cache
from html import escape
from json import dumps
from math import ceil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import azure.functions as func

from src.shared.blob_store import (
    BlobStoreConfigurationError,
    BlobStoreOperationError,
    download_blob_bytes,
    download_blob_to_path,
    upload_pdf_blob,
)
from src.shared.completion_certificate_pdf import (
    CompletionCertificatePdfData,
    format_completion_certificate_number,
    render_completion_certificate_pdf,
)
from src.shared.completion_store import (
    CompletionStoreConfigurationError,
    CompletionStoreOperationError,
    build_completion_cert_request_document,
    build_completion_cert_request_id,
    find_completion_cert_document_for_public_lookup,
    get_completion_cert_requests_container,
    get_completion_records_container,
    has_completed_completion_cert_request_document,
    list_completion_cert_documents,
    read_completed_completion_cert_request_document,
    read_completion_cert_document,
    replace_completion_cert_document,
    upsert_completion_cert_request_document,
)
from src.shared.completion_metrics import (
    read_non_negative_counter,
    summarize_completion_cert_documents,
)
from src.shared.event_store import (
    EventStoreConfigurationError,
    EventStoreOperationError,
    get_events_container,
    increment_event_completion_metrics,
    list_public_event_documents,
    read_public_event_document,
    read_event_completion_metrics,
    replace_event_completion_metrics,
)
from src.shared.datetime_values import parse_utc_iso_datetime
from src.shared.i18n import get_home_page_context, localized_response_headers, resolve_locale
from src.shared.public_lookup_store import (
    PublicLookupStoreConfigurationError,
    PublicLookupStoreOperationError,
    build_public_lookup_attempt_id,
    clear_public_lookup_local_block,
    get_public_lookup_attempts_container,
    is_public_lookup_blocked,
    is_public_lookup_blocked_by_local_cache,
    read_public_lookup_cached_attempt_document,
    read_public_lookup_attempt_document,
    record_public_lookup_failure,
    record_public_lookup_not_available,
    record_public_lookup_success,
    remember_public_lookup_attempt_document,
    remember_public_lookup_block,
)
from src.shared.tax_receipt_store import (
    TaxReceiptStoreConfigurationError,
    TaxReceiptStoreOperationError,
    get_tax_receipts_container,
    list_tax_receipt_documents_by_tax_id,
)
from src.shared.tax_receipt_download_ticket import build_tax_receipt_download_ticket
from src.shared.templates import render_html_template

blueprint = func.Blueprint()
LOGGER = logging.getLogger(__name__)
PUBLIC_LOOKUP_STORE_WAIT_SECONDS = 5
PUBLIC_LOOKUP_STORE_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="public-lookup-store",
)

HOME_PAGE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"
HOME_ALLOWED_DOCUMENT_TYPES = frozenset({"completionCert", "taxReceipt"})
COMPLETION_CERT_SEAL_BLOB_NAME = "completion-cert/organization-seal.png"
COMPLETION_CERT_PREVIEW_BLOB_PREFIX = "completion-cert/previews/png"
COMPLETION_CERT_PREVIEW_IDS = frozenset(
    {
        f"{locale}-{name_display}-{organization_display}.png"
        for locale in ("zh-TW", "en-US")
        for name_display in ("name", "badgeName", "nameWithBadge")
        for organization_display in ("org", "no-org")
    }
)


@lru_cache(maxsize=1)
def load_home_page_template() -> str:
    return HOME_PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_home_page_url_context(req: func.HttpRequest) -> dict[str, str]:
    page_url = _build_absolute_url(req, "/")

    return {
        "canonical_url": page_url,
        "certificate_change_request_api_path": "/api/v1/completion-cert-change-requests",
        "certificate_issue_api_path": "/api/v1/completion-certs/issue",
        "certificate_preview_api_path": "/api/v1/completion-cert-previews",
        "document_lookup_api_path": "/api/v1/document-lookup",
        "events_api_path": "/api/v1/events",
        "page_url": page_url,
        "social_image_url": _build_absolute_url(req, "/assets/logo_sq_b.png"),
        "tax_receipt_download_api_path": "/api/v1/tax-receipts/download",
    }


def build_home_page_event_context(copy: dict[str, str]) -> dict[str, str]:
    events: list[dict[str, Any]] = []
    selected_event = events[0] if events else None
    selected_document_type = ""
    selected_document_type_label = copy["document_type_loading_option"]
    if selected_event is not None and selected_event["documentTypes"]:
        selected_document_type = selected_event["documentTypes"][0]
        selected_document_type_label = resolve_home_document_type_label(
            selected_document_type,
            copy,
        )

    if selected_event is None:
        selected_document_type = "completionCert"
    selected_event_document_types = selected_event["documentTypes"] if selected_event else None
    use_static_document_type = (
        selected_event_document_types is not None
        and len(selected_event_document_types) <= 1
    )

    return {
        "event_name_control_html": build_home_event_name_control_html(
            events,
            copy["event_name_loading_option"],
        ),
        "document_type_options_html": build_home_document_type_options_html(
            copy,
            selected_document_type,
            selected_event_document_types,
        ),
        "document_type_value": selected_document_type,
        "document_type_value_label": selected_document_type_label,
        "document_type_static_hidden_attr": "" if use_static_document_type else " hidden",
        "document_type_trigger_hidden_attr": " hidden" if use_static_document_type else "",
    }


def list_home_page_events() -> list[dict[str, Any]]:
    try:
        event_documents = list_public_event_documents(container=get_events_container())
    except (EventStoreConfigurationError, EventStoreOperationError):
        return []

    return normalize_home_event_documents(event_documents)


def normalize_home_event_documents(
    event_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event_document in event_documents:
        event_id = str(event_document.get("id", "")).strip()
        event_name = str(event_document.get("name", "")).strip()
        document_types = normalize_home_event_document_types(
            event_document.get("documentTypes")
        )
        if not event_id or not event_name:
            continue

        events.append(
            {
                "id": event_id,
                "name": event_name,
                "documentTypes": document_types,
            }
        )

    return events


def build_public_events_json_payload() -> dict[str, Any]:
    event_documents = list_public_event_documents(container=get_events_container())
    return {"events": normalize_home_event_documents(event_documents)}


def build_home_api_json_response(
    payload: dict[str, Any],
    *,
    status_code: int = 200,
) -> func.HttpResponse:
    return func.HttpResponse(
        body=dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
        charset="utf-8",
        headers={
            "Cache-Control": "no-store",
        },
    )


def build_home_api_error_response(
    status_code: int,
    code: str,
    message: str,
) -> func.HttpResponse:
    return build_home_api_json_response(
        {
            "error": {
                "code": code,
                "message": message,
            },
        },
        status_code=status_code,
    )


def get_home_api_message(req: func.HttpRequest, key: str) -> str:
    return get_home_page_context(resolve_locale(req))[key]


def resolve_public_lookup_client_ip(req: func.HttpRequest) -> str | None:
    forwarded_for = _resolve_forwarded_value(req, "X-Forwarded-For")
    return normalize_public_lookup_client_ip(forwarded_for)


def normalize_public_lookup_client_ip(value: str | None) -> str | None:
    if not value:
        return None

    client_ip = value.strip().strip("\"'")
    if not client_ip:
        return None

    if client_ip.startswith("["):
        closing_bracket_index = client_ip.find("]")
        if closing_bracket_index > 1:
            return client_ip[1:closing_bracket_index]

    if client_ip.count(":") == 1:
        host, port = client_ip.rsplit(":", maxsplit=1)
        if host and port.isdecimal():
            return host

    return client_ip


def parse_document_lookup_payload(req: func.HttpRequest) -> dict[str, Any] | None:
    try:
        payload = req.get_json()
    except ValueError:
        return None

    if not isinstance(payload, dict):
        return None

    document_type = str(payload.get("documentType", "")).strip()
    if document_type not in HOME_ALLOWED_DOCUMENT_TYPES:
        return None

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id:
        return None

    if document_type == "completionCert":
        email = str(payload.get("email", "")).strip()
        registration_number = str(payload.get("registrationNumber", "")).strip()
        if not email or not registration_number.isdecimal():
            return None

        return {
            "documentType": document_type,
            "eventId": event_id,
            "email": email,
            "registrationNumber": int(registration_number),
        }

    business_tax_id = str(payload.get("businessTaxId", "")).strip()
    generated_at = str(payload.get("generatedAt", "")).strip()
    if (
        not business_tax_id.isdecimal()
        or len(business_tax_id) != 8
        or parse_utc_iso_datetime(generated_at) is None
    ):
        return None

    return {
        "documentType": document_type,
        "eventId": event_id,
        "businessTaxId": business_tax_id,
        "generatedAt": generated_at,
    }


def parse_completion_cert_change_request_payload(
    req: func.HttpRequest,
) -> dict[str, Any] | None:
    lookup_payload = parse_document_lookup_payload(req)
    if lookup_payload is None or lookup_payload["documentType"] != "completionCert":
        return None

    try:
        raw_payload = req.get_json()
    except ValueError:
        return None

    if not isinstance(raw_payload, dict):
        return None

    requester_note = str(raw_payload.get("requesterNote", "")).strip()
    if not requester_note or len(requester_note) > 600:
        return None

    return {
        **lookup_payload,
        "requesterNote": requester_note,
    }


def parse_completion_cert_issue_payload(
    req: func.HttpRequest,
) -> dict[str, Any] | None:
    lookup_payload = parse_document_lookup_payload(req)
    if lookup_payload is None or lookup_payload["documentType"] != "completionCert":
        return None

    try:
        raw_payload = req.get_json()
    except ValueError:
        return None

    if not isinstance(raw_payload, dict):
        return None

    name_display = str(raw_payload.get("nameDisplay", "")).strip()
    if name_display not in {"name", "badgeName", "nameWithBadge"}:
        return None

    locale = str(raw_payload.get("locale", "")).strip()
    if locale not in {"zh-TW", "en-US"}:
        locale = "zh-TW"

    return {
        **lookup_payload,
        "locale": locale,
        "nameDisplay": name_display,
        "showOrganization": bool(raw_payload.get("showOrganization", False)),
    }


def lookup_public_document(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload["documentType"] == "taxReceipt":
        return lookup_public_tax_receipts(payload)

    return find_completion_cert_document_for_public_lookup(
        container=get_completion_records_container(),
        email=payload["email"],
        event_id=payload["eventId"],
        number=payload["registrationNumber"],
    )


def lookup_public_tax_receipts(payload: dict[str, Any]) -> dict[str, Any] | None:
    documents = list_tax_receipt_documents_by_tax_id(
        container=get_tax_receipts_container(),
        event_id=payload["eventId"],
        tax_id=payload["businessTaxId"],
    )
    if not any(document.get("generatedAt") == payload["generatedAt"] for document in documents):
        return None

    return {
        "documentType": "taxReceipt",
        "eventId": payload["eventId"],
        "taxId": payload["businessTaxId"],
        "generatedAt": payload["generatedAt"],
        "taxReceipts": [normalize_public_tax_receipt(document) for document in documents],
        "downloadTicket": build_tax_receipt_download_ticket(
            event_id=payload["eventId"],
            receipt_ids=[
                str(document.get("id", "")).strip()
                for document in documents
                if str(document.get("id", "")).strip()
            ],
        ),
    }


def normalize_public_tax_receipt(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("id", "")).strip(),
        "amount": read_public_non_negative_int(document.get("amount")),
        "contentType": str(document.get("contentType", "")).strip(),
        "fileName": str(document.get("fileName", "")).strip(),
        "fileSequence": read_public_non_negative_int(document.get("fileSequence")),
        "fileSize": read_public_non_negative_int(document.get("fileSize")),
        "generatedAt": str(document.get("generatedAt", "")).strip(),
    }


def read_public_non_negative_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, value)
    if isinstance(value, str) and value.strip().isdecimal():
        return max(0, int(value.strip()))
    return 0


def can_public_document_request_changes(document: dict[str, Any]) -> bool:
    cert_status = str(document.get("certStatus", "")).strip() or "notIssued"
    if cert_status != "notIssued":
        return False

    completion_cert_id = str(document.get("id", "")).strip()
    if not completion_cert_id:
        return False

    try:
        return not has_completed_completion_cert_request_document(
            container=get_completion_cert_requests_container(),
            completion_cert_id=completion_cert_id,
        )
    except (CompletionStoreConfigurationError, CompletionStoreOperationError):
        LOGGER.warning("Completion cert request status check is unavailable.", exc_info=True)
        return True


def read_public_document_completed_change_request(document: dict[str, Any]) -> dict[str, str] | None:
    completion_cert_id = str(document.get("id", "")).strip()
    if not completion_cert_id:
        return None

    try:
        request_document = read_completed_completion_cert_request_document(
            container=get_completion_cert_requests_container(),
            completion_cert_id=completion_cert_id,
        )
    except (CompletionStoreConfigurationError, CompletionStoreOperationError):
        LOGGER.warning("Completion cert completed request lookup is unavailable.", exc_info=True)
        return None

    if request_document is None:
        return None

    status = str(request_document.get("status", "")).strip()
    if status not in {"approved", "rejected"}:
        return None

    return {
        "status": status,
        "reviewedAt": str(request_document.get("reviewedAt", "")).strip(),
        "reviewNote": str(request_document.get("reviewNote", "")).strip(),
    }


def submit_completion_cert_change_request(payload: dict[str, Any]) -> dict[str, Any]:
    records_container = get_completion_records_container()
    public_document = find_completion_cert_document_for_public_lookup(
        container=records_container,
        email=payload["email"],
        event_id=payload["eventId"],
        number=payload["registrationNumber"],
    )
    if public_document is None:
        raise LookupError("completion certificate was not found")

    cert_status = str(public_document.get("certStatus", "")).strip() or "notIssued"
    if cert_status not in {"notIssued", "changeRequested"}:
        raise PermissionError("completion certificate cannot request changes")

    completion_cert_id = str(public_document.get("id", "")).strip()
    if not completion_cert_id:
        raise CompletionStoreOperationError("Completion certificate record is missing an id.")

    requests_container = get_completion_cert_requests_container()
    if has_completed_completion_cert_request_document(
        container=requests_container,
        completion_cert_id=completion_cert_id,
    ):
        raise PermissionError("completion certificate already has a completed change request")

    request_id = build_completion_cert_request_id(
        payload["requesterNote"],
        completion_cert_id=completion_cert_id,
    )
    request_document = build_completion_cert_request_document(
        completion_cert_id=completion_cert_id,
        event_id=payload["eventId"],
        request_id=request_id,
        requester_email=payload["email"],
        requester_note=payload["requesterNote"],
    )
    saved_request = upsert_completion_cert_request_document(
        container=requests_container,
        document=request_document,
    )

    cert_document = read_completion_cert_document(
        cert_id=completion_cert_id,
        container=records_container,
        event_id=payload["eventId"],
    )
    if str(cert_document.get("certStatus", "")).strip() != "changeRequested":
        cert_document["certStatus"] = "changeRequested"
        cert_document["updatedAt"] = str(saved_request.get("updatedAt", "")).strip()
        replace_completion_cert_document(
            container=records_container,
            document=cert_document,
        )

    return saved_request


def issue_completion_cert_pdf(payload: dict[str, Any], req: func.HttpRequest) -> tuple[bytes, str]:
    records_container = get_completion_records_container()
    public_document = find_completion_cert_document_for_public_lookup(
        container=records_container,
        email=payload["email"],
        event_id=payload["eventId"],
        number=payload["registrationNumber"],
    )
    if public_document is None:
        raise LookupError("completion certificate was not found")

    completion_cert_id = str(public_document.get("id", "")).strip()
    if not completion_cert_id:
        raise CompletionStoreOperationError("Completion certificate record is missing an id.")

    cert_document = read_completion_cert_document(
        cert_id=completion_cert_id,
        container=records_container,
        event_id=payload["eventId"],
    )
    cert_status = str(cert_document.get("certStatus", "")).strip() or "notIssued"
    if cert_status not in {"notIssued", "changeRequested", "issued"}:
        raise PermissionError("completion certificate cannot be issued")

    issued_blob_name = str(cert_document.get("issuedPdfBlobName") or "").strip()
    if cert_status == "issued" and issued_blob_name:
        pdf_bytes = download_blob_bytes(
            container_name=_read_issued_certs_container_name(),
            blob_name=issued_blob_name,
        )
        record_existing_completion_cert_download(
            container=records_container,
            cert_document=cert_document,
        )
        return pdf_bytes, build_completion_cert_download_filename(cert_document)

    event_document = read_public_event_document(
        container=get_events_container(),
        event_id=payload["eventId"],
    )
    if event_document is None:
        raise LookupError("completion certificate event was not found")

    if not _can_issue_completion_cert_for_event(event_document):
        raise PermissionError("completion certificate event is not available")

    verification_token = resolve_completion_cert_verification_token(cert_document)
    cert_pdf_data = build_completion_cert_pdf_data(
        cert_document=cert_document,
        event_document=event_document,
        payload=payload,
        req=req,
        verification_token=verification_token,
    )
    blob_name = build_issued_completion_cert_blob_name(cert_document)
    with tempfile.TemporaryDirectory(prefix="ipg-cert-") as temp_dir:
        temp_path = Path(temp_dir)
        seal_path = temp_path / "organization-seal.png"
        download_blob_to_path(
            container_name=_read_document_assets_container_name(),
            blob_name=_read_completion_cert_seal_blob_name(),
            output_path=seal_path,
        )
        output_path = temp_path / "completion-certificate.pdf"
        render_completion_certificate_pdf(
            CompletionCertificatePdfData(
                **{
                    **cert_pdf_data.__dict__,
                    "seal_image_path": seal_path,
                }
            ),
            output_path,
        )
        pdf_bytes = output_path.read_bytes()

    upload_pdf_blob(
        container_name=_read_issued_certs_container_name(),
        blob_name=blob_name,
        data=pdf_bytes,
    )
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    cert_document["certStatus"] = "issued"
    cert_document["issuedAt"] = now
    cert_document["issuedPdfBlobName"] = blob_name
    cert_document["verificationTokenHash"] = verification_token
    cert_document["certificateDisplayName"] = cert_pdf_data.recipient_name
    cert_document["certificateDisplayOrganization"] = cert_pdf_data.organization
    cert_document["certificateLocale"] = cert_pdf_data.locale
    apply_completion_cert_download_stats(cert_document, now=now)
    cert_document["updatedAt"] = now
    replace_completion_cert_document(
        container=records_container,
        document=cert_document,
    )
    update_completion_metrics_after_document_change(
        records_container=records_container,
        event_id=payload["eventId"],
        deltas={
            "downloadableCount": 1,
            "downloadCount": 1,
            "pendingCount": -1,
        },
    )
    return pdf_bytes, build_completion_cert_download_filename(cert_document)


def record_existing_completion_cert_download(
    *,
    container: Any,
    cert_document: dict[str, Any],
) -> None:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    apply_completion_cert_download_stats(cert_document, now=now)
    cert_document["updatedAt"] = now
    try:
        replace_completion_cert_document(
            container=container,
            document=cert_document,
        )
    except CompletionStoreOperationError:
        LOGGER.warning("Completion certificate download count update failed.", exc_info=True)
        return

    event_id = str(cert_document.get("eventId") or "").strip()
    if event_id:
        update_completion_metrics_after_document_change(
            records_container=container,
            event_id=event_id,
            deltas={"downloadCount": 1},
        )


def update_completion_metrics_after_document_change(
    *,
    records_container: Any,
    event_id: str,
    deltas: dict[str, int],
) -> None:
    try:
        events_container = get_events_container()
        if (
            read_event_completion_metrics(
                container=events_container,
                event_id=event_id,
            )
            is None
        ):
            documents = list_completion_cert_documents(
                container=records_container,
                event_id=event_id,
            )
            replace_event_completion_metrics(
                container=events_container,
                event_id=event_id,
                metrics=summarize_completion_cert_documents(documents),
            )
            return

        increment_event_completion_metrics(
            container=events_container,
            event_id=event_id,
            deltas=deltas,
        )
    except (
        CompletionStoreConfigurationError,
        CompletionStoreOperationError,
        EventStoreConfigurationError,
        EventStoreOperationError,
        Exception,
    ):
        LOGGER.warning("Completion certificate aggregate metrics update failed.", exc_info=True)


def apply_completion_cert_download_stats(
    cert_document: dict[str, Any],
    *,
    now: str,
) -> None:
    cert_document["downloadCount"] = read_non_negative_counter(
        cert_document.get("downloadCount")
    ) + 1
    if not str(cert_document.get("firstDownloadAt") or "").strip():
        cert_document["firstDownloadAt"] = now
    cert_document["lastDownloadAt"] = now


def build_completion_cert_pdf_data(
    *,
    cert_document: dict[str, Any],
    event_document: dict[str, Any],
    payload: dict[str, Any],
    req: func.HttpRequest,
    verification_token: str,
) -> CompletionCertificatePdfData:
    certificate_number = format_completion_certificate_number(
        cert_document.get("number", payload["registrationNumber"]),
        str(cert_document.get("kktixId", "")).strip(),
    )
    return CompletionCertificatePdfData(
        certificate_number=certificate_number,
        recipient_name=resolve_completion_cert_display_name(
            cert_document=cert_document,
            name_display=payload["nameDisplay"],
        ),
        organization=(
            str(cert_document.get("organization", "")).strip()
            if payload["showOrganization"]
            else ""
        ),
        event_name=str(event_document.get("name", "")).strip(),
        event_period_text=format_completion_cert_event_period(
            event_document=event_document,
            locale=payload["locale"],
        ),
        completion_hours=int(event_document.get("completionHours") or 0),
        issued_date_text="",
        verification_url=_build_absolute_url(req, f"/verify/{verification_token}"),
        locale=payload["locale"],
    )


def resolve_completion_cert_verification_token(cert_document: dict[str, Any]) -> str:
    existing_token = str(cert_document.get("verificationTokenHash") or "").strip()
    if existing_token:
        return existing_token

    return generate_completion_cert_verification_token()


def generate_completion_cert_verification_token() -> str:
    return uuid4().hex


def resolve_completion_cert_display_name(
    *,
    cert_document: dict[str, Any],
    name_display: str,
) -> str:
    name = str(cert_document.get("name", "")).strip()
    badge_name = str(cert_document.get("badgeName", "")).strip()
    if name_display == "badgeName" and badge_name:
        return badge_name
    if name_display == "nameWithBadge" and name and badge_name and name != badge_name:
        return f"{name} ({badge_name})"
    return name or badge_name


def format_completion_cert_event_period(
    *,
    event_document: dict[str, Any],
    locale: str,
) -> str:
    start_date = str(event_document.get("eventStartDate", "")).strip()
    end_date = str(event_document.get("eventEndDate", "")).strip()
    if not start_date and not end_date:
        return ""

    formatted_start = format_completion_cert_event_date(start_date, locale=locale)
    formatted_end = format_completion_cert_event_date(end_date, locale=locale)
    if formatted_start and formatted_end and formatted_start != formatted_end:
        return f"{formatted_start} - {formatted_end}"

    return formatted_start or formatted_end


def format_completion_cert_event_date(value: str, *, locale: str) -> str:
    if not value:
        return ""

    normalized_value = value[:10]
    try:
        parsed_date = datetime.strptime(normalized_value, "%Y-%m-%d")
    except ValueError:
        return value

    if locale == "en-US":
        return parsed_date.strftime("%b %-d, %Y")

    return parsed_date.strftime("%Y/%m/%d")


def build_issued_completion_cert_blob_name(cert_document: dict[str, Any]) -> str:
    event_id = str(cert_document.get("eventId", "")).strip()
    cert_id = str(cert_document.get("id", "")).strip()
    return f"{event_id}/{cert_id}.pdf"


def build_completion_cert_download_filename(cert_document: dict[str, Any]) -> str:
    return "certificate.pdf"


def _can_issue_completion_cert_for_event(event_document: dict[str, Any]) -> bool:
    if str(event_document.get("status", "")).strip() != "open":
        return False

    document_types = event_document.get("documentTypes")
    if not isinstance(document_types, list) or "completionCert" not in document_types:
        return False

    download_starts_at = str(
        event_document.get("completionCertDownloadStartsAt") or ""
    ).strip()
    if not download_starts_at:
        return True

    parsed_download_starts_at = parse_utc_iso_datetime(download_starts_at)
    if parsed_download_starts_at is None:
        return True

    return parsed_download_starts_at <= datetime.now(timezone.utc)


def is_completion_cert_lookup_available(payload: dict[str, Any]) -> bool | None:
    if payload["documentType"] != "completionCert":
        return True

    event_document = read_public_event_document(
        container=get_events_container(),
        event_id=payload["eventId"],
    )
    if event_document is None:
        return None

    if str(event_document.get("status", "")).strip() != "open":
        return None

    document_types = event_document.get("documentTypes")
    if not isinstance(document_types, list) or "completionCert" not in document_types:
        return None

    download_starts_at = str(
        event_document.get("completionCertDownloadStartsAt") or ""
    ).strip()
    if not download_starts_at:
        return True

    parsed_download_starts_at = parse_utc_iso_datetime(download_starts_at)
    if parsed_download_starts_at is None:
        return True

    return parsed_download_starts_at <= datetime.now(timezone.utc)


def build_document_lookup_not_found_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        404,
        "document_not_found",
        get_home_api_message(req, "lookup_not_found_message"),
    )


def build_document_lookup_not_available_yet_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        403,
        "document_not_available_yet",
        get_home_api_message(req, "lookup_not_available_yet_message"),
    )


def build_document_lookup_blocked_response(
    req: func.HttpRequest,
    attempt_document: dict[str, Any] | None = None,
) -> func.HttpResponse:
    return build_home_api_error_response(
        429,
        "lookup_blocked",
        build_document_lookup_blocked_message(attempt_document, req=req),
    )


def build_document_lookup_blocked_message(
    attempt_document: dict[str, Any] | None,
    *,
    req: func.HttpRequest | None = None,
) -> str:
    home_copy = (
        get_home_page_context(resolve_locale(req))
        if req is not None
        else get_home_page_context("zh-TW")
    )
    blocked_message = home_copy["lookup_blocked_message"]
    if not attempt_document:
        return blocked_message

    blocked_until = _parse_utc_iso(str(attempt_document.get("blockedUntil", "")))
    if blocked_until is None:
        return blocked_message

    remaining_seconds = (blocked_until - datetime.now(timezone.utc)).total_seconds()
    if remaining_seconds <= 0:
        return blocked_message

    if remaining_seconds < 3600:
        remaining_minutes = max(1, ceil(remaining_seconds / 60))
        return home_copy["lookup_blocked_remaining_minutes_message_template"].format(
            minutes=remaining_minutes,
        )

    remaining_hours = ceil(remaining_seconds / 3600)
    return home_copy["lookup_blocked_remaining_hours_message_template"].format(
        hours=remaining_hours,
    )


def build_document_lookup_unavailable_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        503,
        "lookup_unavailable",
        get_home_api_message(req, "lookup_unavailable_message"),
    )


def build_change_request_invalid_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        400,
        "invalid_change_request",
        get_home_api_message(req, "certificate_change_request_invalid_message"),
    )


def build_change_request_forbidden_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        403,
        "same_origin_required",
        get_home_api_message(req, "certificate_change_request_forbidden_message"),
    )


def build_change_request_not_allowed_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        409,
        "change_request_not_allowed",
        get_home_api_message(req, "certificate_change_request_not_allowed_message"),
    )


def build_change_request_unavailable_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        503,
        "change_request_unavailable",
        get_home_api_message(req, "certificate_change_request_unavailable_message"),
    )


def build_cert_issue_invalid_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        400,
        "invalid_certificate_issue",
        get_home_api_message(req, "certificate_issue_invalid_message"),
    )


def build_cert_issue_forbidden_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        403,
        "same_origin_required",
        get_home_api_message(req, "certificate_issue_forbidden_message"),
    )


def build_cert_issue_not_allowed_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        409,
        "certificate_issue_not_allowed",
        get_home_api_message(req, "certificate_issue_not_allowed_message"),
    )


def build_cert_issue_unavailable_response(req: func.HttpRequest) -> func.HttpResponse:
    return build_home_api_error_response(
        503,
        "certificate_issue_unavailable",
        get_home_api_message(req, "certificate_issue_unavailable_message"),
    )


def build_completion_cert_pdf_response(
    pdf_bytes: bytes,
    *,
    filename: str,
) -> func.HttpResponse:
    return func.HttpResponse(
        body=pdf_bytes,
        status_code=200,
        mimetype="application/pdf",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


def build_completion_cert_preview_image_response(image_bytes: bytes) -> func.HttpResponse:
    return func.HttpResponse(
        body=image_bytes,
        status_code=200,
        mimetype="image/png",
        headers={
            "Cache-Control": "public, max-age=3600",
        },
    )


def read_completion_cert_preview_image(preview_id: str) -> bytes:
    normalized_preview_id = preview_id.strip()
    if normalized_preview_id not in COMPLETION_CERT_PREVIEW_IDS:
        raise LookupError("completion certificate preview was not found")

    return download_blob_bytes(
        container_name=_read_document_assets_container_name(),
        blob_name=f"{COMPLETION_CERT_PREVIEW_BLOB_PREFIX}/{normalized_preview_id}",
    )


def read_public_lookup_attempt_document_without_blocking(
    *,
    attempt_id: str,
) -> dict[str, Any] | None:
    cached_document = read_public_lookup_cached_attempt_document(attempt_id=attempt_id)
    if cached_document is not None:
        return cached_document

    future = PUBLIC_LOOKUP_STORE_EXECUTOR.submit(
        _read_public_lookup_attempt_document_for_cache,
        attempt_id,
    )
    try:
        return future.result(timeout=PUBLIC_LOOKUP_STORE_WAIT_SECONDS)
    except TimeoutError:
        future.add_done_callback(_cache_public_lookup_attempt_document_from_future)
        return None
    except PublicLookupStoreConfigurationError:
        LOGGER.warning("Public lookup attempt store is not configured.", exc_info=True)
        return None
    except PublicLookupStoreOperationError:
        LOGGER.warning("Public lookup attempt store is unavailable.", exc_info=True)
        return None


def schedule_public_lookup_failure_record(
    *,
    attempt_id: str,
    attempt_document: dict[str, Any] | None,
    ip_address: str,
) -> dict[str, Any] | None:
    future = PUBLIC_LOOKUP_STORE_EXECUTOR.submit(
        _record_public_lookup_failure_for_cache,
        attempt_id,
        attempt_document,
        ip_address,
    )
    try:
        return future.result(timeout=PUBLIC_LOOKUP_STORE_WAIT_SECONDS)
    except TimeoutError:
        return None


def schedule_public_lookup_not_available_record(
    *,
    attempt_id: str,
    attempt_document: dict[str, Any] | None,
    ip_address: str,
) -> dict[str, Any] | None:
    future = PUBLIC_LOOKUP_STORE_EXECUTOR.submit(
        _record_public_lookup_not_available_for_cache,
        attempt_id,
        attempt_document,
        ip_address,
    )
    try:
        return future.result(timeout=PUBLIC_LOOKUP_STORE_WAIT_SECONDS)
    except TimeoutError:
        return None


def schedule_public_lookup_success_record(
    *,
    attempt_id: str,
    ip_address: str,
) -> None:
    future = PUBLIC_LOOKUP_STORE_EXECUTOR.submit(
        _record_public_lookup_success_for_cache,
        attempt_id,
        ip_address,
    )
    try:
        future.result(timeout=PUBLIC_LOOKUP_STORE_WAIT_SECONDS)
    except TimeoutError:
        return


def _read_public_lookup_attempt_document_for_cache(
    attempt_id: str,
) -> dict[str, Any] | None:
    attempt_document = read_public_lookup_attempt_document(
        attempt_id=attempt_id,
        container=get_public_lookup_attempts_container(),
    )
    if attempt_document is not None:
        remember_public_lookup_attempt_document(
            attempt_id=attempt_id,
            attempt_document=attempt_document,
        )
        if attempt_id is not None and is_public_lookup_blocked(attempt_document=attempt_document):
            remember_public_lookup_block(
                attempt_id=attempt_id,
                attempt_document=attempt_document,
            )

    return attempt_document


def _record_public_lookup_failure_for_cache(
    attempt_id: str,
    attempt_document: dict[str, Any] | None,
    ip_address: str,
) -> dict[str, Any] | None:
    try:
        updated_attempt_document = record_public_lookup_failure(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
            existing_document=attempt_document,
            ip_address=ip_address,
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning(
            "Public lookup failure count could not be recorded.",
            exc_info=True,
        )
        return None

    remember_public_lookup_attempt_document(
        attempt_id=attempt_id,
        attempt_document=updated_attempt_document,
    )
    if is_public_lookup_blocked(attempt_document=updated_attempt_document):
        remember_public_lookup_block(
            attempt_id=attempt_id,
            attempt_document=updated_attempt_document,
        )

    return updated_attempt_document


def _record_public_lookup_not_available_for_cache(
    attempt_id: str,
    attempt_document: dict[str, Any] | None,
    ip_address: str,
) -> dict[str, Any] | None:
    try:
        updated_attempt_document = record_public_lookup_not_available(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
            existing_document=attempt_document,
            ip_address=ip_address,
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning(
            "Public lookup not-available count could not be recorded.",
            exc_info=True,
        )
        return None

    remember_public_lookup_attempt_document(
        attempt_id=attempt_id,
        attempt_document=updated_attempt_document,
    )
    if is_public_lookup_blocked(attempt_document=updated_attempt_document):
        remember_public_lookup_block(
            attempt_id=attempt_id,
            attempt_document=updated_attempt_document,
        )

    return updated_attempt_document


def _record_public_lookup_success_for_cache(
    attempt_id: str,
    ip_address: str,
) -> None:
    try:
        updated_attempt_document = record_public_lookup_success(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
            ip_address=ip_address,
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning(
            "Public lookup failure count could not be reset after success.",
            exc_info=True,
        )
        return

    remember_public_lookup_attempt_document(
        attempt_id=attempt_id,
        attempt_document=updated_attempt_document,
    )


def _cache_public_lookup_attempt_document_from_future(
    future: Future[dict[str, Any] | None],
) -> None:
    try:
        future.result()
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning("Public lookup attempt store is unavailable.", exc_info=True)


def _parse_utc_iso(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def normalize_home_event_document_types(document_types: Any) -> list[str]:
    if not isinstance(document_types, list):
        return []

    normalized_document_types: list[str] = []
    for document_type in document_types:
        normalized_document_type = str(document_type).strip()
        if (
            normalized_document_type in HOME_ALLOWED_DOCUMENT_TYPES
            and normalized_document_type not in normalized_document_types
        ):
            normalized_document_types.append(normalized_document_type)

    return normalized_document_types


def build_home_event_name_control_html(
    events: list[dict[str, Any]],
    empty_event_name: str,
) -> str:
    if not events:
        return (
            '<input id="event-name" name="eventName" type="hidden" value="">'
            '<div class="field-static-value" id="event-name-value">'
            f"{escape(empty_event_name)}"
            "</div>"
        )

    selected_event = events[0]
    if len(events) == 1:
        return (
            '<input id="event-name" name="eventName" type="hidden" '
            f'value="{escape(selected_event["name"], quote=True)}" '
            f'data-event-id="{escape(selected_event["id"], quote=True)}" '
            "data-event-document-types="
            f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
            '<div class="field-static-value" id="event-name-value" '
            "data-event-document-types="
            f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
            f"{escape(selected_event['name'])}"
            "</div>"
        )

    options_html: list[str] = []
    for index, event in enumerate(events):
        selected_class = " is-selected" if index == 0 else ""
        aria_selected = "true" if index == 0 else "false"
        options_html.append(
            (
                f'<button class="custom-select-option{selected_class}" '
                f'type="button" role="option" aria-selected="{aria_selected}" '
                f'data-value="{escape(event["name"], quote=True)}" '
                f'data-event-id="{escape(event["id"], quote=True)}" '
                "data-event-document-types="
                f'"{escape(",".join(event["documentTypes"]), quote=True)}">'
                f"{escape(event['name'])}"
                "</button>"
            )
        )

    return (
        '<div class="custom-select" id="event-name-select">'
        '<input id="event-name" name="eventName" type="hidden" '
        f'value="{escape(selected_event["name"], quote=True)}" '
        f'data-event-id="{escape(selected_event["id"], quote=True)}" '
        "data-event-document-types="
        f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
        '<button class="custom-select-trigger" id="event-name-trigger" '
        'type="button" aria-expanded="false" aria-haspopup="listbox" '
        'aria-controls="event-name-options" '
        'aria-labelledby="event-name-label event-name-value">'
        '<span id="event-name-value" class="custom-select-value">'
        f"{escape(selected_event['name'])}"
        "</span>"
        '<span class="select-caret" aria-hidden="true"></span>'
        "</button>"
        '<div class="custom-select-menu" id="event-name-options" role="listbox" hidden>'
        f"{''.join(options_html)}"
        "</div>"
        "</div>"
    )


def build_home_document_type_options_html(
    copy: dict[str, str],
    selected_document_type: str,
    available_document_types: list[str] | None,
) -> str:
    options = [
        ("completionCert", "document_type_completion_cert"),
        ("taxReceipt", "document_type_tax_receipt"),
    ]
    options_html: list[str] = []

    for document_type, label_key in options:
        is_available = (
            available_document_types is None or document_type in available_document_types
        )
        is_selected = document_type == selected_document_type
        selected_class = " is-selected" if is_selected else ""
        aria_selected = "true" if is_selected else "false"
        hidden_attr = " hidden" if not is_available else ""
        options_html.append(
            (
                f'<button class="custom-select-option{selected_class}" '
                f'type="button" role="option" aria-selected="{aria_selected}"{hidden_attr} '
                f'data-value="{document_type}" data-label-key="{label_key}">'
                f"{escape(copy[label_key])}"
                "</button>"
            )
        )

    return "".join(options_html)


def resolve_home_document_type_label(document_type: str, copy: dict[str, str]) -> str:
    if document_type == "taxReceipt":
        return copy["document_type_tax_receipt"]

    return copy["document_type_completion_cert"]


def _build_absolute_url(req: func.HttpRequest, path: str) -> str:
    request_url = urlsplit(req.url)
    scheme = _resolve_forwarded_value(req, "X-Forwarded-Proto") or request_url.scheme or "https"
    host = _resolve_forwarded_value(req, "X-Forwarded-Host") or request_url.netloc
    normalized_path = path if path.startswith("/") else f"/{path}"

    return urlunsplit((scheme, host, normalized_path, "", ""))


def _is_same_origin_request(req: func.HttpRequest) -> bool:
    origin = req.headers.get("Origin")
    if not origin:
        return True

    parsed_origin = urlsplit(origin.strip())
    if not parsed_origin.scheme or not parsed_origin.netloc:
        return False

    expected_url = urlsplit(_build_absolute_url(req, "/"))
    return (
        parsed_origin.scheme.lower() == expected_url.scheme.lower()
        and parsed_origin.netloc.lower() == expected_url.netloc.lower()
    )


def _read_document_assets_container_name() -> str:
    container_name = os.getenv("BLOB_DOCUMENT_ASSETS_CONTAINER", "").strip()
    if not container_name:
        raise BlobStoreConfigurationError(
            "Blob Storage document assets container is not configured. "
            "Set BLOB_DOCUMENT_ASSETS_CONTAINER."
        )
    return container_name


def _read_issued_certs_container_name() -> str:
    container_name = os.getenv("BLOB_ISSUED_CERT_CONTAINER", "").strip()
    if not container_name:
        raise BlobStoreConfigurationError(
            "Blob Storage issued certificate container is not configured. Set BLOB_ISSUED_CERT_CONTAINER."
        )
    return container_name


def _read_completion_cert_seal_blob_name() -> str:
    return os.getenv(
        "COMPLETION_CERT_SEAL_BLOB_NAME",
        COMPLETION_CERT_SEAL_BLOB_NAME,
    ).strip() or COMPLETION_CERT_SEAL_BLOB_NAME


def _resolve_forwarded_value(req: func.HttpRequest, header_name: str) -> str | None:
    header_value = req.headers.get(header_name)
    if not header_value:
        return None

    first_value = header_value.split(",", maxsplit=1)[0].strip()
    return first_value or None


@blueprint.function_name(name="home_page")
@blueprint.route(
    route="/",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def home_page(req: func.HttpRequest) -> func.HttpResponse:
    locale = resolve_locale(req)
    home_page_context = get_home_page_context(locale)
    context = {
        **home_page_context,
        **build_home_page_event_context(home_page_context),
        **build_home_page_url_context(req),
    }
    html = render_html_template(
        load_home_page_template(),
        context,
    )

    return func.HttpResponse(
        body=html,
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers=localized_response_headers(locale),
    )


@blueprint.function_name(name="public_events_list_api")
@blueprint.route(
    route="api/v1/events",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_events_list_api(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = build_public_events_json_payload()
    except EventStoreConfigurationError:
        return build_home_api_error_response(
            503,
            "event_store_not_configured",
            get_home_api_message(req, "event_list_unavailable_message"),
        )
    except EventStoreOperationError:
        return build_home_api_error_response(
            503,
            "event_store_unavailable",
            get_home_api_message(req, "event_list_unavailable_message"),
        )

    return build_home_api_json_response(payload)


@blueprint.function_name(name="public_document_lookup_api")
@blueprint.route(
    route="api/v1/document-lookup",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_document_lookup_api(req: func.HttpRequest) -> func.HttpResponse:
    client_ip = resolve_public_lookup_client_ip(req)
    attempt_id = build_public_lookup_attempt_id(client_ip) if client_ip else None
    if attempt_id is not None and is_public_lookup_blocked_by_local_cache(attempt_id=attempt_id):
        return build_document_lookup_blocked_response(
            req,
            read_public_lookup_cached_attempt_document(attempt_id=attempt_id),
        )

    try:
        attempt_document = (
            read_public_lookup_attempt_document_without_blocking(attempt_id=attempt_id)
            if attempt_id is not None
            else None
        )
        if is_public_lookup_blocked(attempt_document=attempt_document):
            remember_public_lookup_block(
                attempt_id=attempt_id,
                attempt_document=attempt_document or {},
            )
            return build_document_lookup_blocked_response(req, attempt_document)

        payload = parse_document_lookup_payload(req)
        lookup_available = (
            is_completion_cert_lookup_available(payload)
            if payload is not None
            else None
        )
        if lookup_available is False:
            updated_attempt_document = (
                schedule_public_lookup_not_available_record(
                    attempt_id=attempt_id,
                    attempt_document=attempt_document,
                    ip_address=client_ip,
                )
                if attempt_id is not None and client_ip is not None
                else None
            )
            if attempt_id is not None and is_public_lookup_blocked(attempt_document=updated_attempt_document):
                remember_public_lookup_block(
                    attempt_id=attempt_id,
                    attempt_document=updated_attempt_document or {},
                )
                return build_document_lookup_blocked_response(req, updated_attempt_document)

            return build_document_lookup_not_available_yet_response(req)

        document = lookup_public_document(payload) if payload else None
        if document is None:
            updated_attempt_document = (
                schedule_public_lookup_failure_record(
                    attempt_id=attempt_id,
                    attempt_document=attempt_document,
                    ip_address=client_ip,
                )
                if attempt_id is not None and client_ip is not None
                else None
            )
            if attempt_id is not None and is_public_lookup_blocked(attempt_document=updated_attempt_document):
                remember_public_lookup_block(
                    attempt_id=attempt_id,
                    attempt_document=updated_attempt_document or {},
                )
                return build_document_lookup_blocked_response(req, updated_attempt_document)

            return build_document_lookup_not_found_response(req)

        if attempt_id is not None and client_ip is not None:
            schedule_public_lookup_success_record(
                attempt_id=attempt_id,
                ip_address=client_ip,
            )
            clear_public_lookup_local_block(attempt_id=attempt_id)
    except (
        CompletionStoreConfigurationError,
        CompletionStoreOperationError,
        EventStoreConfigurationError,
        EventStoreOperationError,
        TaxReceiptStoreConfigurationError,
        TaxReceiptStoreOperationError,
    ):
        return build_document_lookup_unavailable_response(req)

    if payload["documentType"] == "taxReceipt":
        return build_home_api_json_response(
            {
                "document": {
                    "status": "found",
                    "documentType": "taxReceipt",
                    "eventId": document["eventId"],
                    "taxId": document["taxId"],
                    "generatedAt": document["generatedAt"],
                    "taxReceipts": document["taxReceipts"],
                    "downloadTicket": document["downloadTicket"],
                },
            }
        )

    completed_change_request = read_public_document_completed_change_request(document)
    document_payload = {
        "status": "found",
        "documentType": payload["documentType"],
        "badgeName": str(document.get("badgeName", "")).strip(),
        "canRequestChanges": can_public_document_request_changes(document),
        "certStatus": str(document.get("certStatus", "")).strip()
        or "notIssued",
        "name": str(document.get("name", "")).strip(),
        "organization": str(document.get("organization", "")).strip(),
    }
    if completed_change_request is not None:
        document_payload["changeRequestReview"] = completed_change_request

    return build_home_api_json_response(
        {
            "document": document_payload,
        }
    )


@blueprint.function_name(name="public_completion_cert_change_request_api")
@blueprint.route(
    route="api/v1/completion-cert-change-requests",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_completion_cert_change_request_api(req: func.HttpRequest) -> func.HttpResponse:
    if not _is_same_origin_request(req):
        return build_change_request_forbidden_response(req)

    payload = parse_completion_cert_change_request_payload(req)
    if payload is None:
        return build_change_request_invalid_response(req)

    try:
        request_document = submit_completion_cert_change_request(payload)
    except LookupError:
        return build_document_lookup_not_found_response(req)
    except PermissionError:
        return build_change_request_not_allowed_response(req)
    except (CompletionStoreConfigurationError, CompletionStoreOperationError):
        return build_change_request_unavailable_response(req)

    return build_home_api_json_response(
        {
            "changeRequest": {
                "id": request_document["id"],
                "status": request_document["status"],
                "completionCertId": request_document["completionCertId"],
                "eventId": request_document["eventId"],
                "createdAt": request_document["createdAt"],
                "updatedAt": request_document["updatedAt"],
            },
        },
        status_code=201,
    )


@blueprint.function_name(name="public_completion_cert_issue_api")
@blueprint.route(
    route="api/v1/completion-certs/issue",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_completion_cert_issue_api(req: func.HttpRequest) -> func.HttpResponse:
    if not _is_same_origin_request(req):
        return build_cert_issue_forbidden_response(req)

    payload = parse_completion_cert_issue_payload(req)
    if payload is None:
        return build_cert_issue_invalid_response(req)

    try:
        pdf_bytes, filename = issue_completion_cert_pdf(payload, req)
    except LookupError:
        return build_document_lookup_not_found_response(req)
    except PermissionError:
        return build_cert_issue_not_allowed_response(req)
    except (
        BlobStoreConfigurationError,
        BlobStoreOperationError,
        CompletionStoreConfigurationError,
        CompletionStoreOperationError,
        EventStoreConfigurationError,
        EventStoreOperationError,
        ValueError,
    ):
        LOGGER.warning("Completion certificate issue failed.", exc_info=True)
        return build_cert_issue_unavailable_response(req)

    return build_completion_cert_pdf_response(pdf_bytes, filename=filename)


@blueprint.function_name(name="public_completion_cert_preview_api")
@blueprint.route(
    route="api/v1/completion-cert-previews/{preview_id}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_completion_cert_preview_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    preview_id = str(req.route_params.get("preview_id", "")).strip()
    try:
        image_bytes = read_completion_cert_preview_image(preview_id)
    except LookupError:
        return build_home_api_error_response(
            404,
            "certificate_preview_not_found",
            get_home_api_message(req, "lookup_not_found_message"),
        )
    except (BlobStoreConfigurationError, BlobStoreOperationError):
        LOGGER.warning("Completion certificate preview failed.", exc_info=True)
        return build_home_api_error_response(
            503,
            "certificate_preview_unavailable",
            get_home_api_message(req, "lookup_unavailable_message"),
        )

    return build_completion_cert_preview_image_response(image_bytes)
