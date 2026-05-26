from __future__ import annotations

import logging
from datetime import datetime, timezone
from functools import lru_cache
from html import escape
from pathlib import Path
from typing import Any

import azure.functions as func

from src.functions.assets import build_asset_url_context
from src.shared.completion_certificate_pdf import format_completion_certificate_number
from src.shared.completion_store import (
    CompletionStoreConfigurationError,
    CompletionStoreOperationError,
    find_issued_completion_cert_document_by_verification_token,
    get_completion_records_container,
    list_completion_cert_documents,
    read_completion_cert_document,
    replace_completion_cert_document,
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
    read_public_event_document,
    read_event_completion_metrics,
    replace_event_completion_metrics,
)
from src.shared.i18n import (
    HTML_LANGUAGE_TAG_BY_LOCALE,
    LOCALE_COOKIE_MAX_AGE_SECONDS,
    LOCALE_COOKIE_NAME,
    OPEN_GRAPH_LOCALE_BY_LOCALE,
    Locale,
    build_locale_options_html,
    get_verify_page_copy,
    get_verify_page_i18n_json,
    load_locale_catalog,
    localized_response_headers,
    resolve_locale,
)
from src.shared.templates import render_html_template
from src.shared.volunteer_service_store import (
    VolunteerServiceStoreConfigurationError,
    VolunteerServiceStoreOperationError,
    find_issued_volunteer_service_cert_document_by_verification_token,
    get_volunteer_service_certs_container,
    read_volunteer_service_cert_document,
    replace_volunteer_service_cert_document,
)

blueprint = func.Blueprint()
LOGGER = logging.getLogger(__name__)

VERIFY_PAGE_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "verify_completion_cert.html"
)


@lru_cache(maxsize=1)
def load_verify_page_template() -> str:
    return VERIFY_PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


@blueprint.function_name(name="verify_cert_page")
@blueprint.route(
    route="verify/{certId}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def verify_cert_page(req: func.HttpRequest) -> func.HttpResponse:
    locale = resolve_locale(req)
    verification_token = req.route_params.get("certId", "").strip()
    result = build_verify_page_result(verification_token=verification_token)
    context = build_verify_page_context(req=req, locale=locale, result=result)

    return func.HttpResponse(
        body=render_html_template(load_verify_page_template(), context),
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers={
            **localized_response_headers(locale),
            "Cache-Control": "no-store",
        },
    )


def build_verify_page_result(*, verification_token: str) -> dict[str, Any]:
    if not verification_token:
        return {"kind": "invalid"}

    try:
        records_container = get_completion_records_container()
        cert_document = find_issued_completion_cert_document_by_verification_token(
            container=records_container,
            verification_token=verification_token,
        )
    except (CompletionStoreConfigurationError, CompletionStoreOperationError):
        return {"kind": "unavailable"}

    document_type = "completionCert"
    if cert_document is None:
        try:
            volunteer_container = get_volunteer_service_certs_container()
            cert_document = find_issued_volunteer_service_cert_document_by_verification_token(
                container=volunteer_container,
                verification_token=verification_token,
            )
            document_type = "volunteerServiceCert"
        except VolunteerServiceStoreConfigurationError:
            return {"kind": "invalid"}
        except VolunteerServiceStoreOperationError:
            return {"kind": "unavailable"}

    if cert_document is None:
        return {"kind": "invalid"}

    if document_type == "volunteerServiceCert":
        cert_document = record_volunteer_service_cert_verification(
            container=volunteer_container,
            cert_document=cert_document,
        )
    else:
        cert_document = record_completion_cert_verification(
            container=records_container,
            cert_document=cert_document,
        )

    event_name = ""
    event_id = str(cert_document.get("eventId") or "").strip()
    if event_id:
        try:
            event_document = read_public_event_document(
                container=get_events_container(),
                event_id=event_id,
            )
        except (EventStoreConfigurationError, EventStoreOperationError):
            event_document = None
        if event_document is not None:
            event_name = str(event_document.get("name") or "").strip()

    return {
        "kind": "valid",
        "certificateNumber": _format_certificate_number(cert_document),
        "recipientName": str(cert_document.get("certificateDisplayName") or "").strip(),
        "organization": str(
            cert_document.get("certificateDisplayOrganization") or ""
        ).strip(),
        "eventName": event_name,
        "issuedAt": str(cert_document.get("issuedAt") or "").strip(),
    }


def record_completion_cert_verification(
    *,
    container: Any,
    cert_document: dict[str, Any],
) -> dict[str, Any]:
    event_id = str(cert_document.get("eventId") or "").strip()
    cert_id = str(cert_document.get("id") or "").strip()
    if not event_id or not cert_id:
        return cert_document

    try:
        full_document = read_completion_cert_document(
            cert_id=cert_id,
            container=container,
            event_id=event_id,
        )
        full_document["verificationCount"] = read_non_negative_counter(
            full_document.get("verificationCount")
        ) + 1
        full_document["updatedAt"] = utc_now_iso()
        replace_completion_cert_document(
            container=container,
            document=full_document,
        )
        update_completion_metrics_after_verification(
            records_container=container,
            event_id=event_id,
        )
        return full_document
    except CompletionStoreOperationError:
        LOGGER.warning("Completion certificate verification count update failed.", exc_info=True)
        return cert_document


def record_volunteer_service_cert_verification(
    *,
    container: Any,
    cert_document: dict[str, Any],
) -> dict[str, Any]:
    event_id = str(cert_document.get("eventId") or "").strip()
    cert_id = str(cert_document.get("id") or "").strip()
    if not event_id or not cert_id:
        return cert_document

    try:
        full_document = read_volunteer_service_cert_document(
            cert_id=cert_id,
            container=container,
            event_id=event_id,
        )
        full_document["verificationCount"] = read_non_negative_counter(
            full_document.get("verificationCount")
        ) + 1
        full_document["updatedAt"] = utc_now_iso()
        replace_volunteer_service_cert_document(
            container=container,
            document=full_document,
        )
        return full_document
    except VolunteerServiceStoreOperationError:
        LOGGER.warning("Volunteer service certificate verification count update failed.", exc_info=True)
        return cert_document


def update_completion_metrics_after_verification(
    *,
    records_container: Any,
    event_id: str,
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
            deltas={"verificationCount": 1},
        )
    except (
        CompletionStoreConfigurationError,
        CompletionStoreOperationError,
        EventStoreConfigurationError,
        EventStoreOperationError,
        Exception,
    ):
        LOGGER.warning("Completion certificate aggregate metrics update failed.", exc_info=True)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_verify_page_context(
    *,
    req: func.HttpRequest,
    locale: Locale,
    result: dict[str, Any],
) -> dict[str, str]:
    copy = get_verify_page_copy(locale)
    result_kind = str(result["kind"])
    empty_value = copy["empty_value"]
    status_value_by_kind = {
        "valid": copy["status_valid"],
        "invalid": copy["status_invalid"],
        "unavailable": copy["status_unavailable"],
    }

    return {
        **copy,
        **build_asset_url_context(
            "favicon.png",
            "locale-switcher.js",
            "logo_b_alpha.png",
            "logo_sq_b.png",
            "theme.css",
            "verify.css",
            "verify.js",
        ),
        "current_locale": locale,
        "current_locale_label": load_locale_catalog(locale).locale_option_labels[locale],
        "html_lang": HTML_LANGUAGE_TAG_BY_LOCALE[locale],
        "locale_cookie_max_age": str(LOCALE_COOKIE_MAX_AGE_SECONDS),
        "locale_cookie_name": LOCALE_COOKIE_NAME,
        "locale_options_html": build_locale_options_html(
            locale,
            load_locale_catalog(locale).locale_option_labels,
        ),
        "open_graph_locale": OPEN_GRAPH_LOCALE_BY_LOCALE[locale],
        "verify_page_i18n_json": get_verify_page_i18n_json(),
        "result_kind": result_kind,
        "result_title": copy[f"{result_kind}_title"],
        "result_summary": copy[f"{result_kind}_summary"],
        "status_value": status_value_by_kind[result_kind],
        "top_status_label_html": build_top_status_label_html(
            result_kind=result_kind,
            status_label=copy["status_label"],
        ),
        "verification_details_html": build_verification_details_html(
            copy=copy,
            result=result,
            result_kind=result_kind,
            status_value=status_value_by_kind[result_kind],
        ),
        "certificate_number": _read_display_value(result, "certificateNumber", empty_value),
        "recipient_name": _read_display_value(result, "recipientName", empty_value),
        "organization": _read_display_value(result, "organization", empty_value),
        "event_name": _read_display_value(result, "eventName", empty_value),
    }


def build_top_status_label_html(
    *,
    result_kind: str,
    status_label: str,
) -> str:
    if result_kind in {"invalid", "valid"}:
        return ""

    return f'<p class="status-label" id="status-label">{escape(status_label, quote=True)}</p>'


def build_verification_details_html(
    *,
    copy: dict[str, str],
    result: dict[str, Any],
    result_kind: str,
    status_value: str,
) -> str:
    rows = [("status", copy["status_label"], status_value)]
    if result_kind == "invalid":
        rows.extend(
            [
                (
                    "certificateNumber",
                    copy["certificate_number_label"],
                    copy["empty_value"],
                ),
                ("eventName", copy["event_name_label"], copy["empty_value"]),
                ("recipientName", copy["recipient_name_label"], copy["empty_value"]),
                ("issuedAt", copy["issued_at_label"], copy["empty_value"]),
            ]
        )

    if result_kind == "valid":
        rows.extend(
            [
                (
                    "certificateNumber",
                    copy["certificate_number_label"],
                    _read_display_value(
                        result,
                        "certificateNumber",
                        copy["empty_value"],
                    ),
                ),
                (
                    "eventName",
                    copy["event_name_label"],
                    _read_display_value(result, "eventName", copy["empty_value"]),
                ),
                (
                    "recipientName",
                    copy["recipient_name_label"],
                    _read_display_value(result, "recipientName", copy["empty_value"]),
                ),
            ]
        )
        organization = str(result.get("organization") or "").strip()
        if organization:
            rows.insert(4, ("organization", copy["organization_label"], organization))
        issued_at_html = build_local_datetime_html(
            iso_value=str(result.get("issuedAt") or "").strip(),
            empty_value=copy["empty_value"],
        )
        if issued_at_html:
            rows.append(("issuedAt", copy["issued_at_label"], issued_at_html))

    return "".join(
        (
            f'<div data-detail-key="{escape(key, quote=True)}">'
            f'<dt class="verification-detail-label">{escape(label, quote=True)}</dt>'
            '<dd class="verification-detail-value">'
            f"{value if _is_safe_detail_html(value) else escape(value, quote=True)}"
            "</dd>"
            "</div>"
        )
        for key, label, value in rows
    )

def build_local_datetime_html(
    *,
    iso_value: str,
    empty_value: str,
) -> str:
    fallback_value = format_utc_issued_at_fallback(iso_value)
    if not fallback_value:
        return escape(empty_value, quote=True)

    return (
        '<time class="local-datetime" '
        f'datetime="{escape(iso_value, quote=True)}">'
        f"{escape(fallback_value, quote=True)}"
        "</time>"
    )


def format_utc_issued_at_fallback(iso_value: str) -> str:
    try:
        issued_at = datetime.strptime(iso_value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return ""

    return issued_at.strftime("%Y / %m / %d %H:%M UTC")


def _is_safe_detail_html(value: str) -> bool:
    return value.startswith('<time class="local-datetime" ')


def _read_display_value(
    result: dict[str, Any],
    key: str,
    empty_value: str,
) -> str:
    value = str(result.get(key) or "").strip()
    return value or empty_value


def _format_certificate_number(cert_document: dict[str, Any]) -> str:
    try:
        return format_completion_certificate_number(
            cert_document.get("number", ""),
            str(cert_document.get("kktixId") or "").strip(),
        )
    except ValueError:
        return ""
