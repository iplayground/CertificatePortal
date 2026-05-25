from __future__ import annotations

import base64
import binascii
import csv
import hashlib
import hmac
import io
import json
import logging
import os
import time
import zipfile
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date, timedelta
from functools import lru_cache
from html import escape
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import azure.functions as func

from src.functions.assets import asset_url, build_asset_url_context
from src.shared.portal_auth import (
    PORTAL_GOOGLE_SESSION_COOKIE_NAME,
    PortalGoogleAuthError,
    PortalAccess,
    build_portal_google_auth_callback_response,
    build_portal_google_auth_start_response,
    build_portal_google_logout_response,
    build_portal_login_url,
    build_portal_logout_url,
    is_portal_auth_bypass_enabled,
    is_portal_google_auth_configured,
    is_portal_google_group_auth_configured,
    resolve_portal_access,
)
from src.shared.datetime_values import parse_utc_iso_datetime
from src.shared.blob_store import (
    BlobStoreConfigurationError,
    BlobStoreOperationError,
    delete_blob,
    download_blob_bytes,
    upload_blob_bytes,
)
from src.shared.completion_store import (
    CompletionStoreConfigurationError,
    CompletionStoreOperationError,
    build_completion_cert_document,
    build_completion_cert_id,
    get_completion_cert_requests_container,
    get_completion_records_container,
    list_completion_cert_request_documents,
    list_completion_cert_documents,
    read_completion_cert_document,
    read_completion_cert_request_document,
    replace_completion_cert_document,
    replace_completion_cert_request_document,
    upsert_completion_cert_documents,
)
from src.shared.completion_metrics import (
    read_non_negative_int_field,
    summarize_completion_cert_documents,
)
from src.shared.event_store import (
    EventStoreConfigurationError,
    EventStoreOperationError,
    build_event_document,
    build_event_id,
    create_event_document,
    get_events_container,
    list_event_documents,
    normalize_event_completion_metrics,
    replace_event_completion_metrics,
    update_event_document,
    utc_now_iso,
)
from src.shared.page_alerts import (
    DEFAULT_PAGE_ALERT_CONTEXT,
    build_page_alert_html,
    resolve_page_alert_dismiss_delay_ms,
)
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
    record_public_lookup_success,
    remember_public_lookup_attempt_document,
    remember_public_lookup_block,
)
from src.shared.tax_receipt_store import (
    TaxReceiptStoreConfigurationError,
    TaxReceiptStoreOperationError,
    build_tax_receipt_blob_name,
    build_tax_receipt_document,
    build_tax_receipt_file_name,
    build_tax_receipt_id,
    count_tax_receipt_queried_companies,
    delete_tax_receipt_document,
    get_tax_receipts_container,
    list_tax_receipt_documents,
    read_tax_receipt_document,
    replace_tax_receipt_document,
    upsert_tax_receipt_document,
)
from src.shared.tax_receipt_download_ticket import (
    is_valid_tax_receipt_download_ticket,
    read_tax_receipt_download_ticket_payload,
)
from src.shared.templates import render_html_template
from src.shared.volunteer_service_store import (
    VolunteerServiceStoreConfigurationError,
    VolunteerServiceStoreOperationError,
    build_volunteer_service_cert_document,
    build_volunteer_service_cert_id,
    create_volunteer_service_cert_document,
    get_volunteer_service_certs_container,
    list_volunteer_service_cert_documents,
    read_volunteer_service_cert_document,
    replace_volunteer_service_cert_document,
)

blueprint = func.Blueprint()
LOGGER = logging.getLogger(__name__)

PORTAL_ENTRY_PATH = "/portal"
PORTAL_DASHBOARD_PATH = "/portal/dashboard"
PORTAL_HOME_PATH = "/"
PORTAL_FLASH_COOKIE_NAME = "portal_flash"
PORTAL_FLASH_MAX_AGE_SECONDS = 60
PORTAL_GOOGLE_LOGIN_CANCELLED_ERROR = "google-login-cancelled"
PORTAL_GOOGLE_LOGIN_DATA_AUTHORIZATION_REQUIRED_ERROR = "google-login-data-authorization-required"
PORTAL_GOOGLE_LOGIN_FAILED_ERROR = "google-login-failed"
PORTAL_GOOGLE_LOGIN_AUTHORIZATION_CHECK_FAILED_ERROR = "google-login-authorization-check-failed"
PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR = "google-login-not-authorized"
PORTAL_LOGIN_ALERT_DISMISS_DELAY_MS_BY_ERROR_CODE = {
    DEFAULT_PAGE_ALERT_CONTEXT: None,
}
PORTAL_API_CSRF_MAX_AGE_SECONDS = 28800
PORTAL_API_CSRF_HEADER_NAME = "X-Portal-CSRF-Token"
PORTAL_API_IDEMPOTENCY_HEADER_NAME = "Idempotency-Key"
PORTAL_ALLOWED_EVENT_STATUSES = frozenset({"open", "unlisted"})
PORTAL_ALLOWED_EVENT_DOCUMENT_TYPES = frozenset(
    {"completionCert", "volunteerServiceCert", "taxReceipt"}
)
PORTAL_COMPLETION_CSV_ALIASES = {
    "badgeName": ("你是誰，ID 或具有鑑識度的名稱 Name on Badge",),
    "email": ("Email", "email"),
    "kktixId": ("Id",),
    "name": ("姓名 Full Name",),
    "number": ("報名序號",),
    "organization": ("服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)",),
    "ticketName": ("票種",),
}
PORTAL_COMPLETION_CSV_REQUIRED_FIELDS = frozenset(
    {"badgeName", "email", "kktixId", "number", "ticketName"}
)
PORTAL_COMPLETION_CSV_REQUIRED_COLUMNS = frozenset(
    {*PORTAL_COMPLETION_CSV_REQUIRED_FIELDS, "name", "organization"}
)
PORTAL_COMPLETION_CSV_FIELD_LABELS = {
    "badgeName": "Badge Name",
    "email": "Email",
    "kktixId": "Id",
    "name": "姓名 Full Name",
    "number": "報名序號",
    "organization": "公司名",
    "ticketName": "票種",
}
PORTAL_COMPLETION_CERT_MUTABLE_FIELDS = frozenset(
    {"attendanceStatus", "certStatus", "email", "name", "organization"}
)
PORTAL_COMPLETION_CERT_REQUIRED_MUTABLE_FIELDS = frozenset(
    {"email"}
)
PORTAL_COMPLETION_CERT_ALLOWED_ATTENDANCE_STATUSES = frozenset(
    {"checkedIn", "notCheckedIn"}
)
PORTAL_COMPLETION_CERT_REVOKE_FIELDS = frozenset({"certStatus"})
PORTAL_COMPLETION_CERT_DATA_FIELDS = frozenset({"email", "name", "organization"})
PORTAL_COMPLETION_CERT_REQUEST_ALLOWED_REVIEW_STATUSES = frozenset(
    {"approved", "rejected"}
)
PORTAL_TAX_RECEIPT_ALLOWED_CONTENT_TYPES = frozenset(
    {"application/pdf", "image/png", "image/jpeg"}
)
PORTAL_TAX_RECEIPT_MAX_FILE_BYTES = 10 * 1024 * 1024
PUBLIC_TAX_RECEIPT_DOWNLOAD_COOLDOWN_SECONDS = 300
PORTAL_LOGIN_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_login.html"
PORTAL_DASHBOARD_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_dashboard.html"
PORTAL_DASHBOARD_WELCOME_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_welcome.html"
)
PORTAL_DASHBOARD_COMPLETION_CERTS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "portal_dashboard_completion_certs.html"
)
PORTAL_DASHBOARD_COMPLETION_REVIEWS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "portal_dashboard_completion_reviews.html"
)
PORTAL_DASHBOARD_VOLUNTEER_SERVICE_CERTS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "portal_dashboard_volunteer_service_certs.html"
)
PORTAL_DASHBOARD_TAX_RECEIPTS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "templates"
    / "portal_dashboard_tax_receipts.html"
)
PORTAL_DASHBOARD_EVENTS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_events.html"
)
PORTAL_EVENT_STORE_PREWARM_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="portal-event-store-prewarm",
)
PORTAL_EVENT_STORE_PREWARM_FUTURES: list[Future[object]] = []


@lru_cache(maxsize=1)
def load_portal_login_template() -> str:
    return PORTAL_LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_template() -> str:
    return PORTAL_DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_welcome_template() -> str:
    return PORTAL_DASHBOARD_WELCOME_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_completion_certs_template() -> str:
    return PORTAL_DASHBOARD_COMPLETION_CERTS_TEMPLATE_PATH.read_text(
        encoding="utf-8"
    )


@lru_cache(maxsize=1)
def load_portal_dashboard_completion_reviews_template() -> str:
    return PORTAL_DASHBOARD_COMPLETION_REVIEWS_TEMPLATE_PATH.read_text(
        encoding="utf-8"
    )


@lru_cache(maxsize=1)
def load_portal_dashboard_volunteer_service_certs_template() -> str:
    return PORTAL_DASHBOARD_VOLUNTEER_SERVICE_CERTS_TEMPLATE_PATH.read_text(
        encoding="utf-8"
    )


@lru_cache(maxsize=1)
def load_portal_dashboard_tax_receipts_template() -> str:
    return PORTAL_DASHBOARD_TAX_RECEIPTS_TEMPLATE_PATH.read_text(
        encoding="utf-8"
    )


@lru_cache(maxsize=1)
def load_portal_dashboard_events_template() -> str:
    return PORTAL_DASHBOARD_EVENTS_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_portal_page_response(body: str, *, cookie_header: str | None = None) -> func.HttpResponse:
    headers = {
        "Content-Language": "zh-TW",
        "Cache-Control": "no-store",
        "X-Robots-Tag": "noindex, nofollow",
    }
    if cookie_header is not None:
        headers["Set-Cookie"] = cookie_header

    return func.HttpResponse(
        body=body,
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers=headers,
    )


def build_portal_redirect_response(
    location: str,
    *,
    cookie_header: str | None = None,
) -> func.HttpResponse:
    headers = {
        "Cache-Control": "no-store",
        "Location": location,
    }
    if cookie_header is not None:
        headers["Set-Cookie"] = cookie_header

    return func.HttpResponse(
        body="",
        status_code=302,
        headers=headers,
    )


def build_portal_home_link_html() -> str:
    return (
        f'<a class="secondary-button portal-action-link" href="{PORTAL_HOME_PATH}" '
        'data-loading-label="返回首頁中...">'
        "返回首頁"
        "</a>"
    )


def build_portal_feedback_html(message: str) -> str:
    return (
        '<div class="form-feedback is-error" id="form-feedback" role="status" aria-live="polite">'
        f"{escape(message)}"
        "</div>"
    )


def resolve_portal_login_error_message(error_code: str) -> str:
    if error_code == PORTAL_GOOGLE_LOGIN_CANCELLED_ERROR:
        return "已取消 Google 登入。若仍需進入管理平台，請再試一次。"
    if error_code == PORTAL_GOOGLE_LOGIN_DATA_AUTHORIZATION_REQUIRED_ERROR:
        return "請完成資料授權後再登入。"
    if error_code == PORTAL_GOOGLE_LOGIN_AUTHORIZATION_CHECK_FAILED_ERROR:
        return "群組驗證未完成，請稍後再試。"
    if error_code == PORTAL_GOOGLE_LOGIN_FAILED_ERROR:
        return "Google 登入未完成。請稍後再試一次。"
    if error_code == PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR:
        return "此帳號不在允許群組中，請聯絡管理員。"

    return ""


def resolve_portal_login_error_title(error_code: str) -> str:
    if error_code == PORTAL_GOOGLE_LOGIN_DATA_AUTHORIZATION_REQUIRED_ERROR:
        return "資料授權未完成"
    if error_code == PORTAL_GOOGLE_LOGIN_AUTHORIZATION_CHECK_FAILED_ERROR:
        return "群組驗證未完成"
    if error_code == PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR:
        return "沒有文件管理平台權限"

    return "Google 登入未完成"


def resolve_portal_login_alert_dismiss_delay_ms(error_code: str) -> int | None:
    return resolve_page_alert_dismiss_delay_ms(
        error_code,
        PORTAL_LOGIN_ALERT_DISMISS_DELAY_MS_BY_ERROR_CODE,
    )


def resolve_portal_flash_error_code(req: func.HttpRequest) -> str:
    return _get_cookie_value(req, PORTAL_FLASH_COOKIE_NAME) or ""


def build_portal_login_context(
    req: func.HttpRequest,
    access: PortalAccess,
    *,
    flash_error_code: str = "",
) -> dict[str, str]:
    asset_context = build_asset_url_context(
        "favicon.png",
        "logo_b_alpha.png",
        "page-alert.js",
        "portal.css",
        "portal-login.js",
        "theme.css",
    )
    login_url = build_portal_login_url(req, PORTAL_ENTRY_PATH)
    home_link_html = build_portal_home_link_html()
    lead_html = ""
    feedback_html = ""
    page_alert_html = ""
    portal_google_auth_configured = is_portal_google_auth_configured()
    portal_google_group_auth_configured = is_portal_google_group_auth_configured()
    identity_html = ""

    if not access.principal.is_authenticated:
        portal_error_message = resolve_portal_login_error_message(flash_error_code)
        if portal_error_message:
            page_alert_html = build_page_alert_html(
                title=resolve_portal_login_error_title(flash_error_code),
                message=portal_error_message,
                tone="error",
                dismiss_delay_ms=resolve_portal_login_alert_dismiss_delay_ms(
                    flash_error_code
                ),
            )

        if not portal_google_auth_configured:
            feedback_html = build_portal_feedback_html(
                "Google 登入尚未設定完成。請先設定 PORTAL_GOOGLE_CLIENT_ID 與 "
                "PORTAL_GOOGLE_CLIENT_SECRET，再重新啟動 Azure Functions。"
            )
            primary_action_html = (
                '<button class="submit-button" type="button" disabled aria-disabled="true">'
                "Google 登入尚未設定"
                "</button>"
            )
            secondary_action_html = home_link_html
            return {
                **asset_context,
                "portal_panel_kicker": "管理者登入",
                "page_alert_html": page_alert_html,
                "portal_lead_html": lead_html,
                "portal_feedback_html": feedback_html,
                "portal_identity_html": identity_html,
                "portal_primary_action_html": primary_action_html,
                "portal_secondary_action_html": secondary_action_html,
            }

        if not portal_google_group_auth_configured:
            feedback_html = build_portal_feedback_html(
                "Google 群組授權尚未設定完成。請設定 PORTAL_GOOGLE_ALLOWED_GROUP_KEYS，"
                "再重新啟動 Azure Functions。"
            )
            primary_action_html = (
                '<button class="submit-button" type="button" disabled aria-disabled="true">'
                "Google 群組授權尚未設定"
                "</button>"
            )
            return {
                **asset_context,
                "portal_panel_kicker": "管理者登入",
                "page_alert_html": page_alert_html,
                "portal_lead_html": lead_html,
                "portal_feedback_html": feedback_html,
                "portal_identity_html": identity_html,
                "portal_primary_action_html": primary_action_html,
                "portal_secondary_action_html": home_link_html,
            }

        primary_action_html = (
            f'<a class="portal-sso-button portal-action-link" href="{escape(login_url)}" '
            'data-loading-label="導向 Google 登入中..." aria-label="使用 Google 帳號登入">'
            f'<img class="portal-sso-button-icon" src="{escape(asset_url("google-g-icon.svg"))}" alt="" aria-hidden="true">'
            '<span class="portal-sso-button-copy">'
            '<span class="portal-sso-button-label">使用 Google 繼續</span>'
            "</span>"
            "</a>"
        )
        return {
            **asset_context,
            "portal_panel_kicker": "管理者登入",
            "page_alert_html": page_alert_html,
            "portal_lead_html": lead_html,
            "portal_feedback_html": feedback_html,
            "portal_identity_html": identity_html,
            "portal_primary_action_html": primary_action_html,
            "portal_secondary_action_html": home_link_html,
        }

    return {
        **asset_context,
        "portal_panel_kicker": "管理者登入",
        "page_alert_html": page_alert_html,
        "portal_lead_html": lead_html,
        "portal_feedback_html": feedback_html,
        "portal_identity_html": identity_html,
        "portal_primary_action_html": "",
        "portal_secondary_action_html": home_link_html,
    }


def build_portal_dashboard_context(req: func.HttpRequest, access: PortalAccess) -> dict[str, str]:
    return {
        **build_asset_url_context(
            "favicon.png",
            "logo_b_alpha.png",
            "logo_sq_b.png",
            "page-alert.js",
            "portal.css",
            "portal-dashboard.js",
            "portal-dashboard-completion-certs.js",
            "portal-dashboard-completion-reviews.js",
            "portal-dashboard-events.js",
            "portal-dashboard-tax-receipts.js",
            "portal-dashboard-volunteer-service-certs.js",
            "portal-dashboard-welcome.js",
            "portal-datetime-picker.js",
            "portal-event-cache.js",
            "theme.css",
        ),
        "portal_entry_path": PORTAL_ENTRY_PATH,
        "portal_logout_url": build_portal_logout_url(req, PORTAL_ENTRY_PATH),
        "portal_csrf_token": build_portal_csrf_token(req, access),
        "portal_user_display_name": access.principal.display_name,
    }


def build_portal_dashboard_events_context(
    req: func.HttpRequest,
    access: PortalAccess,
) -> dict[str, str]:
    return build_portal_dashboard_context(req, access)


def schedule_portal_event_store_prewarm() -> None:
    if (
        PORTAL_EVENT_STORE_PREWARM_FUTURES
        and not PORTAL_EVENT_STORE_PREWARM_FUTURES[-1].done()
    ):
        return

    PORTAL_EVENT_STORE_PREWARM_FUTURES[:] = [
        PORTAL_EVENT_STORE_PREWARM_EXECUTOR.submit(get_events_container)
    ]


def build_portal_events_json_payload() -> dict[str, Any]:
    try:
        events = list_event_documents(container=get_events_container())
    except (EventStoreConfigurationError, EventStoreOperationError) as exc:
        raise EventStoreOperationError(str(exc)) from exc

    return {"events": [normalize_portal_event_for_api(event) for event in events]}


def build_portal_dashboard_welcome_context(
    req: func.HttpRequest,
    access: PortalAccess,
) -> dict[str, str]:
    return {
        **build_portal_dashboard_context(req, access),
        **build_portal_welcome_completion_metrics_placeholder_context(),
    }


def build_portal_welcome_completion_metrics_placeholder_context() -> dict[str, str]:
    return {
        "completion_metrics_event_name": "尚無活動資料",
        "completion_total_count": "--",
        "completion_downloadable_count": "--",
        "completion_downloaded_member_count": "--",
        "completion_verification_count": "--",
        "completion_pending_count": "--",
        "tax_receipt_count": "--",
        "tax_receipt_queried_company_count": "--",
        "tax_receipt_download_count": "--",
        "tax_receipt_total_amount": "--",
    }


def build_portal_welcome_metrics_payload() -> dict[str, Any]:
    default_metrics = {
        "eventName": "尚無活動資料",
        "totalCount": 0,
        "downloadableCount": 0,
        "downloadCount": 0,
        "verificationCount": 0,
        "pendingCount": 0,
    }
    default_tax_receipt_metrics = {
        "eventName": "尚無活動資料",
        "receiptCount": 0,
        "queriedCompanyCount": None,
        "downloadCount": 0,
        "totalAmount": 0,
    }

    try:
        events = list_event_documents(container=get_events_container())
        completion_event = resolve_latest_welcome_metrics_event(
            events,
            document_type="completionCert",
        )
        tax_receipt_event = resolve_latest_welcome_metrics_event(
            events,
            document_type="taxReceipt",
        )
        if completion_event is None:
            completion_metrics = default_metrics
        else:
            completion_metrics = build_portal_welcome_completion_metrics(
                completion_event
            )

        if tax_receipt_event is None:
            tax_receipt_metrics = default_tax_receipt_metrics
        else:
            tax_receipt_metrics = build_portal_welcome_tax_receipt_metrics(
                tax_receipt_event
            )
    except (
        CompletionStoreConfigurationError,
        CompletionStoreOperationError,
        EventStoreConfigurationError,
        EventStoreOperationError,
        TaxReceiptStoreConfigurationError,
        TaxReceiptStoreOperationError,
    ) as exc:
        raise EventStoreOperationError(str(exc)) from exc

    return {
        "completionCertMetrics": completion_metrics,
        "taxReceiptMetrics": tax_receipt_metrics,
    }


def build_portal_welcome_completion_metrics(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id", "")).strip()
    if not event_id:
        return {
            "eventName": "尚無活動資料",
            "totalCount": 0,
            "downloadableCount": 0,
            "downloadCount": 0,
            "verificationCount": 0,
            "pendingCount": 0,
        }

    summary = normalize_event_completion_metrics(event)
    if summary is None:
        documents = list_completion_cert_documents(
            container=get_completion_records_container(),
            event_id=event_id,
        )
        summary = summarize_completion_cert_documents(documents)
        try:
            replace_event_completion_metrics(
                container=get_events_container(),
                event_id=event_id,
                metrics=summary,
            )
        except (EventStoreConfigurationError, EventStoreOperationError):
            LOGGER.warning("Unable to refresh cached completion metrics.", exc_info=True)

    event_name = str(event.get("name", "")).strip()
    return {
        "eventName": event_name or event_id,
        "totalCount": max(0, int(summary["totalCount"])),
        "downloadableCount": max(0, int(summary["downloadableCount"])),
        "downloadCount": max(0, int(summary["downloadCount"])),
        "verificationCount": max(0, int(summary["verificationCount"])),
        "pendingCount": count_pending_completion_cert_change_requests(),
    }


def count_pending_completion_cert_change_requests() -> int:
    return len(
        list_completion_cert_request_documents(
            container=get_completion_cert_requests_container(),
            status="pending",
        )
    )


def build_portal_welcome_tax_receipt_metrics(event: dict[str, Any]) -> dict[str, Any]:
    event_id = str(event.get("id", "")).strip()
    if not event_id:
        return {
            "eventName": "尚無活動資料",
            "receiptCount": 0,
            "queriedCompanyCount": 0,
            "downloadCount": 0,
            "totalAmount": 0,
        }

    container = get_tax_receipts_container()
    documents = list_tax_receipt_documents(
        container=container,
        event_id=event_id,
    )
    event_name = str(event.get("name", "")).strip()
    return {
        "eventName": event_name or event_id,
        "receiptCount": len(documents),
        "queriedCompanyCount": count_tax_receipt_queried_companies(
            container=container,
            event_id=event_id,
        ),
        "downloadCount": sum(
            read_non_negative_int_field(document, ("downloadCount",))
            for document in documents
        ),
        "totalAmount": sum(
            read_non_negative_int_field(document, ("amount",))
            for document in documents
        ),
    }


def resolve_latest_welcome_metrics_event(
    events: list[dict[str, Any]],
    *,
    document_type: str | None = None,
) -> dict[str, Any] | None:
    open_events: list[tuple[dict[str, Any], date]] = []
    for event in events:
        if str(event.get("status", "")).strip() != "open":
            continue
        if document_type and document_type not in normalize_portal_event_document_types(
            event.get("documentTypes")
        ):
            continue

        event_start_date = parse_event_start_date_for_metrics(event)
        if event_start_date is None:
            continue

        open_events.append((event, event_start_date))

    if not open_events:
        return None

    event, _event_start_date = max(open_events, key=lambda item: item[1])
    return event


def parse_event_start_date_for_metrics(event: dict[str, Any]) -> date | None:
    normalized_value = str(event.get("eventStartDate") or "").strip()
    if not normalized_value:
        return None

    try:
        return date.fromisoformat(normalized_value)
    except ValueError:
        return None


def format_portal_metric_number(value: int) -> str:
    return f"{max(0, value):,}"


def read_portal_event(event_id: str) -> dict[str, Any]:
    try:
        event = get_events_container().read_item(item=event_id, partition_key=event_id)
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            raise EventStoreOperationError("找不到指定活動。") from exc
        raise

    if not isinstance(event, dict):
        raise EventStoreOperationError("活動資料格式不合法。")

    return event


def normalize_portal_event_for_api(event: dict[str, Any]) -> dict[str, Any]:
    event_status = str(event.get("status", "")).strip()
    return {
        "id": str(event.get("id", "")).strip(),
        "name": str(event.get("name", "")).strip(),
        "status": event_status if event_status in PORTAL_ALLOWED_EVENT_STATUSES else "unlisted",
        "documentTypes": normalize_portal_event_document_types(event.get("documentTypes")),
        "volunteerServiceTicketNames": normalize_portal_volunteer_service_ticket_names(
            event.get("volunteerServiceTicketNames")
        ),
        "eventStartDate": str(event.get("eventStartDate") or "").strip(),
        "eventEndDate": str(event.get("eventEndDate") or "").strip(),
        "completionHours": normalize_event_completion_hours(
            event.get("completionHours")
        ),
        "completionCertDownloadStartsAt": str(
            event.get("completionCertDownloadStartsAt") or ""
        ).strip(),
    }


def normalize_portal_volunteer_service_ticket_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    ticket_names: list[str] = []
    for item in value:
        ticket_name = str(item).strip()
        if ticket_name and ticket_name not in ticket_names:
            ticket_names.append(ticket_name)
    return ticket_names


def resolve_completion_ticket_names_for_event(event_id: str) -> list[str]:
    documents = list_completion_cert_documents(
        container=get_completion_records_container(),
        event_id=event_id,
    )
    ticket_names = {
        str(document.get("ticketName", "")).strip()
        for document in documents
        if str(document.get("ticketName", "")).strip()
    }
    return sorted(ticket_names)


def normalize_completion_cert_for_api(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("id", "")).strip(),
        "eventId": str(document.get("eventId", "")).strip(),
        "number": normalize_completion_cert_number(document.get("number")),
        "kktixId": str(document.get("kktixId", "")).strip(),
        "badgeName": str(document.get("badgeName", "")).strip(),
        "ticketName": str(document.get("ticketName", "")).strip(),
        "name": str(document.get("name", "")).strip(),
        "organization": str(document.get("organization", "")).strip(),
        "email": str(document.get("email", "")).strip(),
        "attendanceStatus": str(document.get("attendanceStatus", "")).strip()
        or "notCheckedIn",
        "certStatus": str(document.get("certStatus", "")).strip() or "notIssued",
        "issuedPdfBlobName": document.get("issuedPdfBlobName"),
        "verificationTokenHash": document.get("verificationTokenHash"),
        "verificationCount": read_non_negative_int_field(
            document,
            ("verificationCount",),
        ),
        "issuedAt": document.get("issuedAt"),
        "transferredToDocumentType": document.get("transferredToDocumentType"),
        "transferredToDocumentId": document.get("transferredToDocumentId"),
        "transferredAt": document.get("transferredAt"),
        "createdAt": str(document.get("createdAt", "")).strip(),
    }


def normalize_completion_cert_request_for_api(
    document: dict[str, Any],
    *,
    completion_cert: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "id": str(document.get("id", "")).strip(),
        "completionCertId": str(document.get("completionCertId", "")).strip(),
        "eventId": str(document.get("eventId", "")).strip(),
        "status": str(document.get("status", "")).strip() or "pending",
        "requesterEmail": str(document.get("requesterEmail", "")).strip(),
        "requesterNote": str(document.get("requesterNote", "")).strip(),
        "reviewedBy": document.get("reviewedBy"),
        "reviewedAt": document.get("reviewedAt"),
        "reviewCompletedNotifiedAt": document.get("reviewCompletedNotifiedAt"),
        "reviewNote": document.get("reviewNote"),
        "createdAt": str(document.get("createdAt", "")).strip(),
        "updatedAt": str(document.get("updatedAt", "")).strip(),
    }
    if completion_cert is not None:
        payload["completionCert"] = normalize_completion_cert_for_api(completion_cert)
    return payload


def normalize_volunteer_service_cert_for_api(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(document.get("id", "")).strip(),
        "eventId": str(document.get("eventId", "")).strip(),
        "sourceCompletionCertId": str(document.get("sourceCompletionCertId", "")).strip(),
        "number": normalize_completion_cert_number(document.get("number")),
        "kktixId": str(document.get("kktixId", "")).strip(),
        "badgeName": str(document.get("badgeName", "")).strip(),
        "name": str(document.get("name", "")).strip(),
        "email": str(document.get("email", "")).strip(),
        "serviceOrganization": document.get("serviceOrganization"),
        "serviceHours": document.get("serviceHours"),
        "serviceStartDate": document.get("serviceStartDate"),
        "serviceEndDate": document.get("serviceEndDate"),
        "downloadEnabled": document.get("downloadEnabled") is True,
        "certStatus": str(document.get("certStatus", "")).strip() or "notIssued",
        "createdAt": str(document.get("createdAt", "")).strip(),
    }


def normalize_tax_receipt_for_api(document: dict[str, Any]) -> dict[str, Any]:
    receipt_id = str(document.get("id", "")).strip()
    event_id = str(document.get("eventId", "")).strip()
    return {
        "id": receipt_id,
        "eventId": event_id,
        "taxId": str(document.get("taxId", "")).strip(),
        "amount": read_non_negative_int_field(document, ("amount",)),
        "generatedAt": str(document.get("generatedAt", "")).strip(),
        "sourceBlobName": str(document.get("sourceBlobName", "")).strip(),
        "fileName": str(document.get("fileName", "")).strip(),
        "fileSequence": read_non_negative_int_field(document, ("fileSequence",)),
        "contentType": str(document.get("contentType", "")).strip(),
        "fileSize": read_non_negative_int_field(document, ("fileSize",)),
        "downloadCount": read_non_negative_int_field(document, ("downloadCount",)),
        "portalDownloadCount": read_non_negative_int_field(
            document,
            ("portalDownloadCount",),
        ),
        "lastDownloadAt": document.get("lastDownloadAt"),
        "lastPortalDownloadAt": document.get("lastPortalDownloadAt"),
        "createdAt": str(document.get("createdAt", "")).strip(),
        "updatedAt": str(document.get("updatedAt", "")).strip(),
    }


def normalize_completion_cert_number(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0


def parse_completion_csv_payload(
    payload: Any,
) -> tuple[dict[str, Any] | None, str | None, dict[str, Any] | None]:
    if not isinstance(payload, dict):
        return None, "請提供 JSON 物件。", None

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return None, "活動識別碼不合法。", None

    csv_text = str(payload.get("csvText", "")).lstrip("\ufeff")
    if not csv_text.strip():
        return None, "請提供 CSV 內容。", None

    try:
        rows = [
            (line_number, [field.strip() for field in row])
            for line_number, row in enumerate(csv.reader(csv_text.splitlines()), start=1)
            if any(field.strip() for field in row)
        ]
    except csv.Error:
        return None, "CSV 格式不合法。", None

    if not rows:
        return None, "CSV 沒有可匯入的資料。", None

    _, headers = rows[0]
    column_indexes, mapping_error = resolve_completion_csv_column_indexes_from_payload(
        headers,
        payload.get("fieldMapping"),
    )
    if mapping_error:
        return None, mapping_error, None
    missing_fields = [
        field_name
        for field_name in sorted(PORTAL_COMPLETION_CSV_REQUIRED_COLUMNS)
        if column_indexes[field_name] < 0
    ]
    if missing_fields:
        return (
            None,
            f"CSV 缺少必要欄位：{format_completion_csv_field_labels(missing_fields)}。",
            None,
        )

    records: list[dict[str, Any]] = []
    row_errors: list[dict[str, Any]] = []
    for row_number, row in rows[1:]:
        record = {
            field_name: resolve_completion_csv_cell(row, column_index)
            for field_name, column_index in column_indexes.items()
        }
        if not any(record.values()):
            continue

        missing_values = [
            field_name
            for field_name in sorted(PORTAL_COMPLETION_CSV_REQUIRED_FIELDS)
            if not record[field_name]
        ]
        if missing_values:
            missing_value_labels = build_completion_csv_field_labels(missing_values)
            row_errors.append(
                {
                    "rowNumber": row_number,
                    "fields": missing_value_labels,
                    "message": (
                        f"CSV 第 {row_number} 列缺少必要欄位值："
                        f"{'、'.join(missing_value_labels)}。"
                    ),
                }
            )
            continue

        if not record["number"].isdigit():
            row_errors.append(
                {
                    "rowNumber": row_number,
                    "fields": ["報名序號"],
                    "message": f"CSV 第 {row_number} 列報名序號必須是整數。",
                }
            )
            continue

        record["number"] = int(record["number"])

        records.append(record)

    if row_errors:
        return (
            None,
            f"CSV 有 {len(row_errors)} 筆資料需要修正，尚未匯入 DB。",
            {"rowErrors": row_errors},
        )

    if not records:
        return None, "CSV 沒有可匯入的資料。", None

    return {"eventId": event_id, "records": records}, None, None


def format_completion_csv_field_labels(field_names: list[str]) -> str:
    return "、".join(build_completion_csv_field_labels(field_names))


def build_completion_csv_field_labels(field_names: list[str]) -> list[str]:
    return [
        PORTAL_COMPLETION_CSV_FIELD_LABELS.get(field_name, field_name)
        for field_name in field_names
    ]


def resolve_completion_csv_column_indexes(headers: list[str]) -> dict[str, int]:
    return {
        field_name: next(
            (
                headers.index(alias)
                for alias in aliases
                if alias in headers
            ),
            -1,
        )
        for field_name, aliases in PORTAL_COMPLETION_CSV_ALIASES.items()
    }


def resolve_completion_csv_column_indexes_from_payload(
    headers: list[str],
    field_mapping: Any,
) -> tuple[dict[str, int], str | None]:
    if field_mapping is None:
        return resolve_completion_csv_column_indexes(headers), None

    if not isinstance(field_mapping, dict):
        return {}, "CSV 欄位配對格式不合法。"

    column_indexes: dict[str, int] = {}
    for field_name in PORTAL_COMPLETION_CSV_ALIASES:
        raw_index = field_mapping.get(field_name)
        if isinstance(raw_index, bool):
            return {}, "CSV 欄位配對格式不合法。"
        if isinstance(raw_index, int):
            column_index = raw_index
        elif isinstance(raw_index, str) and raw_index.strip().isdigit():
            column_index = int(raw_index.strip())
        else:
            column_index = -1

        if column_index >= len(headers):
            return {}, "CSV 欄位配對超出可用欄位範圍。"
        column_indexes[field_name] = column_index

    return column_indexes, None


def resolve_completion_csv_cell(row: list[str], column_index: int) -> str:
    if column_index < 0 or column_index >= len(row):
        return ""
    return row[column_index].strip()


def build_completion_cert_documents_from_records(
    *,
    event_id: str,
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        build_completion_cert_document(
            badge_name=record.get("badgeName", ""),
            cert_id=build_completion_cert_id(
                event_id=event_id,
                number=record["number"],
                kktix_id=record["kktixId"],
            ),
            email=record["email"],
            event_id=event_id,
            kktix_id=record["kktixId"],
            name=record.get("name", ""),
            number=record["number"],
            organization=record.get("organization", ""),
            ticket_name=record["ticketName"],
        )
        for record in records
    ]


def parse_completion_cert_update_payload(
    payload: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "請提供 JSON 物件。"

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return None, "活動識別碼不合法。"

    updates = {
        field_name: str(payload.get(field_name, "")).strip()
        for field_name in PORTAL_COMPLETION_CERT_MUTABLE_FIELDS
        if field_name in payload
    }
    if not updates:
        return None, "請提供要修改的完訓證明資料。"

    missing_fields = [
        field_name
        for field_name in sorted(PORTAL_COMPLETION_CERT_REQUIRED_MUTABLE_FIELDS)
        if field_name in updates and not updates[field_name]
    ]
    if missing_fields:
        return (
            None,
            f"完訓證明資料缺少必要欄位值："
            f"{format_completion_csv_field_labels(missing_fields)}。",
        )

    attendance_status = updates.get("attendanceStatus")
    if (
        attendance_status is not None
        and attendance_status not in PORTAL_COMPLETION_CERT_ALLOWED_ATTENDANCE_STATUSES
    ):
        return None, "簽到狀態不合法。"

    cert_status = updates.get("certStatus")
    if cert_status is not None and cert_status != "notIssued":
        return None, "完訓證明狀態不合法。"

    if cert_status == "notIssued" and set(updates) != PORTAL_COMPLETION_CERT_REVOKE_FIELDS:
        return None, "撤銷發行請求不可同時修改其他完訓證明資料。"

    return {"eventId": event_id, "updates": updates}, None


def parse_completion_cert_request_review_payload(
    payload: Any,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "請提供 JSON 物件。"

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return None, "活動識別碼不合法。"

    review_status = str(payload.get("status", "")).strip()
    if review_status not in PORTAL_COMPLETION_CERT_REQUEST_ALLOWED_REVIEW_STATUSES:
        return None, "審核狀態不合法。"

    review_note = str(payload.get("reviewNote", "")).strip()
    if len(review_note) > 600:
        return None, "審核備註不可超過 600 字。"

    cert_updates = {}
    if review_status == "approved":
        cert_updates = {
            field_name: str(payload.get(field_name, "")).strip()
            for field_name in PORTAL_COMPLETION_CERT_MUTABLE_FIELDS
            if field_name in payload
        }
        cert_updates.pop("attendanceStatus", None)
        if "email" in cert_updates and not cert_updates["email"]:
            return None, "完訓證明資料缺少必要欄位值：Email。"

    return {
        "eventId": event_id,
        "reviewNote": review_note,
        "status": review_status,
        "updates": cert_updates,
    }, None


def parse_tax_receipt_payload(
    payload: Any,
    *,
    require_file: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "請提供 JSON 物件。"

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return None, "活動識別碼不合法。"

    tax_id = str(payload.get("taxId", "")).strip()
    if not tax_id.isdecimal() or len(tax_id) != 8:
        return None, "統編必須是 8 碼數字。"

    amount_value = payload.get("amount")
    if isinstance(amount_value, bool):
        return None, "金額必須是大於 0 的整數。"
    if isinstance(amount_value, int):
        amount = amount_value
    elif isinstance(amount_value, str) and amount_value.replace(",", "").isdecimal():
        amount = int(amount_value.replace(",", ""))
    else:
        return None, "金額必須是大於 0 的整數。"
    if amount <= 0:
        return None, "金額必須是大於 0 的整數。"

    generated_at = str(payload.get("generatedAt", "")).strip()
    if parse_utc_iso_datetime(generated_at) is None:
        return None, "產製時間必須使用 UTC ISO 8601 格式。"

    file_payload, file_error = parse_tax_receipt_file_payload(
        payload,
        require_file=require_file,
    )
    if file_error is not None:
        return None, file_error

    return {
        "amount": amount,
        "eventId": event_id,
        "file": file_payload,
        "generatedAt": generated_at,
        "taxId": tax_id,
    }, None


def parse_tax_receipt_file_payload(
    payload: dict[str, Any],
    *,
    require_file: bool,
) -> tuple[dict[str, Any] | None, str | None]:
    file_base64_payload = payload.get("fileBase64")
    if file_base64_payload in (None, ""):
        if require_file:
            return None, "請上傳 PDF、PNG 或 JPG 檔案。"
        return None, None

    content_type = str(payload.get("contentType", "")).strip().lower()
    if content_type not in PORTAL_TAX_RECEIPT_ALLOWED_CONTENT_TYPES:
        return None, "檔案格式僅支援 PDF、PNG 或 JPG。"

    file_name = str(payload.get("fileName", "")).strip()
    if not file_name:
        return None, "檔案名稱不可空白。"

    try:
        file_bytes = base64.b64decode(str(file_base64_payload), validate=True)
    except (binascii.Error, ValueError):
        return None, "檔案內容格式不合法。"

    if not file_bytes:
        return None, "檔案不可為空。"
    if len(file_bytes) > PORTAL_TAX_RECEIPT_MAX_FILE_BYTES:
        return None, "檔案大小不可超過 10 MB。"

    return {
        "bytes": file_bytes,
        "contentType": content_type,
        "fileName": file_name,
        "fileSize": len(file_bytes),
    }, None


def get_tax_receipts_blob_container_name() -> str:
    container_name = os.getenv("BLOB_TAX_RECEIPTS_CONTAINER", "").strip()
    if not container_name:
        raise BlobStoreConfigurationError(
            "Blob Storage 繳稅證明容器尚未設定完成。請設定 BLOB_TAX_RECEIPTS_CONTAINER。"
        )
    return container_name


def resolve_next_tax_receipt_file_sequence(
    *,
    container: Any,
    event_id: str,
    tax_id: str,
    exclude_receipt_id: str = "",
) -> int:
    matching_documents = [
        document
        for document in list_tax_receipt_documents(
            container=container,
            event_id=event_id,
        )
        if str(document.get("id", "")).strip() != exclude_receipt_id
        and str(document.get("taxId", "")).strip() == tax_id
    ]
    max_existing_sequence = max(
        (
            read_non_negative_int_field(document, ("fileSequence",))
            for document in matching_documents
        ),
        default=0,
    )
    return max(max_existing_sequence, len(matching_documents)) + 1


def resolve_existing_tax_receipt_file_sequence(
    *,
    container: Any,
    current_document: dict[str, Any],
    event_id: str,
    receipt_id: str,
    tax_id: str,
) -> int:
    file_sequence = read_non_negative_int_field(current_document, ("fileSequence",))
    if file_sequence > 0:
        return file_sequence
    return resolve_next_tax_receipt_file_sequence(
        container=container,
        event_id=event_id,
        exclude_receipt_id=receipt_id,
        tax_id=tax_id,
    )


def ensure_event_supports_tax_receipt(event_id: str) -> None:
    event = read_portal_event(event_id)
    document_types = normalize_portal_event_document_types(event.get("documentTypes"))
    if "taxReceipt" not in document_types:
        raise EventStoreOperationError("指定活動未開放營業稅繳稅證明。")


def build_portal_event_row_html(event: dict[str, Any]) -> str:
    event_name = str(event.get("name", "")).strip()
    event_status = str(event.get("status", "")).strip()
    document_types = normalize_portal_event_document_types(event.get("documentTypes"))
    completion_cert_download_starts_at = str(
        event.get("completionCertDownloadStartsAt") or ""
    ).strip()
    status_label = resolve_portal_event_status_label(event_status)
    document_labels = resolve_portal_event_document_type_labels(document_types)
    document_text = "、".join(document_labels) if document_labels else "未開放文件申請"

    return (
        '<tr class="event-list-row" role="button" tabindex="0" '
        f'aria-label="編輯活動 {escape(event_name, quote=True)}" '
        'data-event-form-open="edit" '
        f'data-event-name="{escape(event_name, quote=True)}" '
        f'data-event-status="{escape(event_status, quote=True)}" '
        f'data-event-document-types="{escape(",".join(document_types), quote=True)}" '
        f'data-event-start-date="{escape(str(event.get("eventStartDate") or "").strip(), quote=True)}" '
        f'data-event-end-date="{escape(str(event.get("eventEndDate") or "").strip(), quote=True)}" '
        f'data-event-completion-hours="{escape(str(normalize_event_completion_hours(event.get("completionHours")) or ""), quote=True)}" '
        'data-event-completion-cert-download-starts-at='
        f'"{escape(completion_cert_download_starts_at, quote=True)}">'
        f"<td>{escape(event_name)}</td>"
        f"<td>{escape(document_text)}</td>"
        f"<td>{escape(status_label)}</td>"
        "</tr>"
    )


def normalize_portal_event_document_types(document_types: Any) -> list[str]:
    if not isinstance(document_types, list):
        return []

    normalized_document_types: list[str] = []
    for document_type in document_types:
        normalized_document_type = str(document_type).strip()
        if (
            normalized_document_type in PORTAL_ALLOWED_EVENT_DOCUMENT_TYPES
            and normalized_document_type not in normalized_document_types
        ):
            normalized_document_types.append(normalized_document_type)
    return normalized_document_types


def resolve_portal_event_document_type_labels(document_types: list[str]) -> list[str]:
    labels = {
        "completionCert": "完訓證明",
        "volunteerServiceCert": "志工服務證明",
        "taxReceipt": "營業稅繳稅證明",
    }
    return [labels[document_type] for document_type in document_types if document_type in labels]


def resolve_portal_event_status_label(status: str) -> str:
    if status == "open":
        return "開放"
    return "下架"


def build_portal_api_json_response(
    payload: dict[str, Any],
    *,
    status_code: int,
) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
    )


def build_portal_api_error_response(
    status_code: int,
    code: str,
    message: str,
    *,
    details: dict[str, Any] | None = None,
) -> func.HttpResponse:
    error_payload: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error_payload["details"] = details

    return build_portal_api_json_response(
        {"error": error_payload},
        status_code=status_code,
    )


def get_portal_api_actor(access: PortalAccess) -> str:
    return access.principal.email or access.principal.user_id or access.principal.display_name


def build_portal_csrf_token(req: func.HttpRequest, access: PortalAccess) -> str:
    payload = {
        "actor": get_portal_api_actor(access),
        "exp": int(time.time()) + PORTAL_API_CSRF_MAX_AGE_SECONDS,
        "session": _get_portal_csrf_session_fingerprint(req),
    }
    encoded_payload = _base64url_encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )
    signature = hmac.new(
        _get_portal_csrf_secret().encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def is_valid_portal_csrf_token(
    req: func.HttpRequest,
    access: PortalAccess,
    token: str,
) -> bool:
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
    except ValueError:
        return False

    expected_signature = hmac.new(
        _get_portal_csrf_secret().encode("utf-8"),
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
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return False

    expected_actor = get_portal_api_actor(access)
    expected_session = _get_portal_csrf_session_fingerprint(req)
    return (
        payload.get("actor") == expected_actor
        and payload.get("session") == expected_session
    )


def require_portal_api_access(req: func.HttpRequest) -> PortalAccess | func.HttpResponse:
    access = resolve_portal_access(req)
    if not access.is_authorized:
        return build_portal_api_error_response(401, "unauthorized", "請先登入管理平台。")

    if not is_same_origin_portal_api_request(req):
        return build_portal_api_error_response(
            403,
            "invalid_origin",
            "此 API 僅接受同源管理平台頁面呼叫。",
        )

    csrf_token = req.headers.get(PORTAL_API_CSRF_HEADER_NAME, "").strip()
    if not csrf_token or not is_valid_portal_csrf_token(req, access, csrf_token):
        return build_portal_api_error_response(
            403,
            "invalid_csrf_token",
            "請重新整理管理平台後再試一次。",
        )

    return access


def require_portal_api_read_access(req: func.HttpRequest) -> PortalAccess | func.HttpResponse:
    access = resolve_portal_access(req)
    if not access.is_authorized:
        return build_portal_api_error_response(401, "unauthorized", "請先登入管理平台。")

    if not is_same_origin_portal_api_request(req):
        return build_portal_api_error_response(
            403,
            "invalid_origin",
            "此 API 僅接受同源管理平台頁面呼叫。",
        )

    return access


def is_authorized_tax_receipt_download_request(
    req: func.HttpRequest,
    *,
    event_id: str,
    receipt_ids: list[str],
    ticket: str,
) -> bool:
    if not is_same_origin_portal_api_request(req):
        return False

    access = resolve_portal_access(req)
    csrf_token = req.headers.get(PORTAL_API_CSRF_HEADER_NAME, "").strip()
    if access.is_authorized and csrf_token and is_valid_portal_csrf_token(req, access, csrf_token):
        return True

    return bool(ticket) and is_valid_tax_receipt_download_ticket(
        ticket=ticket,
        event_id=event_id,
        receipt_ids=receipt_ids,
    )


def is_portal_tax_receipt_download_request(req: func.HttpRequest) -> bool:
    if not is_same_origin_portal_api_request(req):
        return False

    access = resolve_portal_access(req)
    csrf_token = req.headers.get(PORTAL_API_CSRF_HEADER_NAME, "").strip()
    return bool(
        access.is_authorized
        and csrf_token
        and is_valid_portal_csrf_token(req, access, csrf_token)
    )


def resolve_public_download_client_ip(req: func.HttpRequest) -> str | None:
    forwarded_for = req.headers.get("X-Forwarded-For", "").split(",", maxsplit=1)[0].strip()
    return normalize_public_download_client_ip(forwarded_for)


def normalize_public_download_client_ip(value: str | None) -> str | None:
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


def read_public_download_attempt_document(
    *,
    attempt_id: str,
) -> dict[str, Any] | None:
    cached_document = read_public_lookup_cached_attempt_document(attempt_id=attempt_id)
    if cached_document is not None:
        return cached_document

    try:
        attempt_document = read_public_lookup_attempt_document(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning("Public tax receipt download attempt store is unavailable.", exc_info=True)
        return None

    if attempt_document is not None:
        remember_public_lookup_attempt_document(
            attempt_id=attempt_id,
            attempt_document=attempt_document,
        )

    return attempt_document


def build_tax_receipt_download_blocked_response(
    attempt_document: dict[str, Any] | None,
) -> func.HttpResponse:
    return build_portal_api_error_response(
        429,
        "lookup_blocked",
        build_public_download_blocked_message(attempt_document),
    )


def build_public_download_blocked_message(
    attempt_document: dict[str, Any] | None,
) -> str:
    from src.functions.home import build_document_lookup_blocked_message

    return build_document_lookup_blocked_message(attempt_document)


def record_public_download_failure(
    *,
    attempt_id: str | None,
    attempt_document: dict[str, Any] | None,
    client_ip: str | None,
) -> dict[str, Any] | None:
    if attempt_id is None or client_ip is None:
        return None

    try:
        updated_attempt_document = record_public_lookup_failure(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
            existing_document=attempt_document,
            ip_address=client_ip,
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning(
            "Public tax receipt download failure count could not be recorded.",
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


def record_public_download_success(
    *,
    attempt_id: str | None,
    client_ip: str | None,
) -> None:
    if attempt_id is None or client_ip is None:
        return

    try:
        updated_attempt_document = record_public_lookup_success(
            attempt_id=attempt_id,
            container=get_public_lookup_attempts_container(),
            ip_address=client_ip,
        )
    except (PublicLookupStoreConfigurationError, PublicLookupStoreOperationError):
        LOGGER.warning(
            "Public tax receipt download failure count could not be reset after success.",
            exc_info=True,
        )
        return

    remember_public_lookup_attempt_document(
        attempt_id=attempt_id,
        attempt_document=updated_attempt_document,
    )
    clear_public_lookup_local_block(attempt_id=attempt_id)


def is_same_origin_portal_api_request(req: func.HttpRequest) -> bool:
    request_origin = _resolve_request_origin(req)
    origin_header = req.headers.get("Origin", "").strip()
    if origin_header:
        return _normalize_origin(origin_header) == request_origin

    referer_header = req.headers.get("Referer", "").strip()
    if referer_header:
        return _normalize_origin(referer_header) == request_origin

    return False


def parse_create_event_payload(payload: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(payload, dict):
        return None, "請提供 JSON 物件。"

    name = str(payload.get("name", "")).strip()
    if not name:
        return None, "活動名稱不可空白。"

    status = str(payload.get("status", "")).strip()
    if status not in PORTAL_ALLOWED_EVENT_STATUSES:
        return None, "活動狀態不合法。"

    event_start_date, event_start_error = parse_event_date_payload(
        payload.get("eventStartDate"),
        field_label="活動開始日期",
    )
    if event_start_date is None:
        return None, event_start_error

    event_end_date, event_end_error = parse_event_date_payload(
        payload.get("eventEndDate"),
        field_label="活動結束日期",
    )
    if event_end_date is None:
        return None, event_end_error

    if event_end_date < event_start_date:
        return None, "活動結束日期不可早於活動開始日期。"

    document_types_payload = payload.get("documentTypes")
    if not isinstance(document_types_payload, list):
        return None, "可申請文件類型格式不合法。"

    document_types: list[str] = []
    for document_type in document_types_payload:
        normalized_document_type = str(document_type).strip()
        if normalized_document_type not in PORTAL_ALLOWED_EVENT_DOCUMENT_TYPES:
            return None, "可申請文件類型包含不支援的項目。"
        if normalized_document_type not in document_types:
            document_types.append(normalized_document_type)

    completion_starts_at_payload = payload.get("completionCertDownloadStartsAt")
    completion_starts_at = (
        str(completion_starts_at_payload).strip()
        if completion_starts_at_payload is not None
        else ""
    )
    completion_hours, completion_hours_error = parse_optional_completion_hours_payload(
        payload.get("completionHours")
    )
    if completion_hours_error is not None:
        return None, completion_hours_error

    if "completionCert" in document_types:
        if completion_hours is None:
            return None, "完訓總時數必須是正整數。"
        if parse_utc_iso_datetime(completion_starts_at) is None:
            return None, "完訓證明開放下載時間必須使用 UTC ISO 8601 格式。"
    elif completion_starts_at and parse_utc_iso_datetime(completion_starts_at) is None:
        return None, "完訓證明開放下載時間必須使用 UTC ISO 8601 格式。"

    volunteer_service_ticket_names: list[str] | None = None
    if "volunteerServiceTicketNames" in payload:
        ticket_names_payload = payload.get("volunteerServiceTicketNames")
        if not isinstance(ticket_names_payload, list):
            return None, "志工服務證明票種格式不合法。"
        volunteer_service_ticket_names = normalize_portal_volunteer_service_ticket_names(
            ticket_names_payload
        )

    return (
        {
            "name": name,
            "status": status,
            "documentTypes": document_types,
            "eventStartDate": event_start_date.isoformat(),
            "eventEndDate": event_end_date.isoformat(),
            "completionHours": completion_hours,
            "completionCertDownloadStartsAt": completion_starts_at or None,
            "volunteerServiceTicketNames": volunteer_service_ticket_names,
        },
        None,
    )


def parse_event_date_payload(
    value: Any,
    *,
    field_label: str,
) -> tuple[date | None, str | None]:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return None, f"{field_label}不可空白。"

    try:
        parsed_date = date.fromisoformat(normalized_value)
    except ValueError:
        return None, f"{field_label}必須使用 YYYY-MM-DD 格式。"

    if parsed_date.isoformat() != normalized_value:
        return None, f"{field_label}必須使用 YYYY-MM-DD 格式。"

    return parsed_date, None


def parse_completion_hours_payload(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, bool):
        return None, "完訓總時數必須是正整數。"

    if isinstance(value, int):
        completion_hours = value
    elif isinstance(value, str) and value.strip().isdecimal():
        completion_hours = int(value.strip())
    else:
        return None, "完訓總時數必須是正整數。"

    if completion_hours <= 0:
        return None, "完訓總時數必須是正整數。"

    return completion_hours, None


def parse_optional_completion_hours_payload(value: Any) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, str) and value.strip() == "":
        return None, None

    return parse_completion_hours_payload(value)


def normalize_event_completion_hours(value: Any) -> int | None:
    completion_hours, _ = parse_completion_hours_payload(value)
    return completion_hours


def _resolve_request_origin(req: func.HttpRequest) -> str:
    request_url = urlsplit(req.url)
    forwarded_proto = req.headers.get("X-Forwarded-Proto", "").split(",", maxsplit=1)[0].strip()
    forwarded_host = req.headers.get("X-Forwarded-Host", "").split(",", maxsplit=1)[0].strip()
    scheme = forwarded_proto or request_url.scheme
    host = forwarded_host or req.headers.get("Host", "").strip() or request_url.netloc
    return f"{scheme.lower()}://{host.lower()}"


def _normalize_origin(value: str) -> str:
    parsed_value = urlsplit(value)
    if not parsed_value.scheme or not parsed_value.netloc:
        return ""
    return f"{parsed_value.scheme.lower()}://{parsed_value.netloc.lower()}"


def _get_portal_csrf_session_fingerprint(req: func.HttpRequest) -> str:
    session_value = _get_cookie_value(req, PORTAL_GOOGLE_SESSION_COOKIE_NAME)
    if session_value:
        return hashlib.sha256(session_value.encode("utf-8")).hexdigest()

    if is_portal_auth_bypass_enabled():
        bypass_identity = os.getenv("PORTAL_AUTH_BYPASS_EMAIL", "").strip().lower()
        return hashlib.sha256(f"local-dev-bypass:{bypass_identity}".encode("utf-8")).hexdigest()

    return ""


def _get_portal_csrf_secret() -> str:
    configured_secret = os.getenv("PORTAL_CSRF_SECRET", "").strip()
    if configured_secret:
        return configured_secret

    google_client_secret = os.getenv("PORTAL_GOOGLE_CLIENT_SECRET", "").strip()
    if google_client_secret:
        return google_client_secret

    if is_portal_auth_bypass_enabled():
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


def build_portal_google_auth_error_response(
    req: func.HttpRequest,
    error: PortalGoogleAuthError,
) -> func.HttpResponse:
    error_code = error.error_code or PORTAL_GOOGLE_LOGIN_FAILED_ERROR
    if str(error) == "access_denied":
        error_code = PORTAL_GOOGLE_LOGIN_DATA_AUTHORIZATION_REQUIRED_ERROR

    return build_portal_redirect_response(
        PORTAL_ENTRY_PATH,
        cookie_header=_build_portal_set_cookie_header(
            PORTAL_FLASH_COOKIE_NAME,
            error_code,
            max_age=PORTAL_FLASH_MAX_AGE_SECONDS,
            req=req,
        ),
    )


def _build_portal_set_cookie_header(
    cookie_name: str,
    cookie_value: str,
    *,
    max_age: int,
    req: func.HttpRequest,
) -> str:
    parts = [
        f"{cookie_name}={cookie_value}",
        "Path=/portal",
        f"Max-Age={max_age}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if _should_use_secure_cookies(req):
        parts.append("Secure")

    return "; ".join(parts)


def _build_portal_delete_cookie_header(cookie_name: str, *, req: func.HttpRequest) -> str:
    return _build_portal_set_cookie_header(cookie_name, "", max_age=0, req=req)


def _should_use_secure_cookies(req: func.HttpRequest) -> bool:
    request_url = urlsplit(req.url)
    forwarded_proto = req.headers.get("X-Forwarded-Proto", "").split(",", maxsplit=1)[0].strip()
    scheme = forwarded_proto or request_url.scheme or ""
    return scheme.lower() == "https"


def _get_cookie_value(req: func.HttpRequest, cookie_name: str) -> str | None:
    raw_cookie_header = req.headers.get("Cookie", "")
    if not raw_cookie_header:
        return None

    parsed_cookies = SimpleCookie()
    parsed_cookies.load(raw_cookie_header)
    morsel = parsed_cookies.get(cookie_name)
    if morsel is None:
        return None

    cookie_value = morsel.value.strip()
    return cookie_value or None


def require_portal_access(req: func.HttpRequest) -> PortalAccess | func.HttpResponse:
    access = resolve_portal_access(req)
    if access.is_authorized:
        return access

    return build_portal_redirect_response(PORTAL_ENTRY_PATH)


@blueprint.function_name(name="portal_login_page")
@blueprint.route(
    route="portal",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_login_page(req: func.HttpRequest) -> func.HttpResponse:
    flash_error_code = resolve_portal_flash_error_code(req)
    flash_cookie_header = None
    if flash_error_code:
        flash_cookie_header = _build_portal_delete_cookie_header(PORTAL_FLASH_COOKIE_NAME, req=req)

    access = resolve_portal_access(req)
    if access.is_authorized:
        return build_portal_redirect_response(
            PORTAL_DASHBOARD_PATH,
            cookie_header=flash_cookie_header,
        )

    html = render_html_template(
        load_portal_login_template(),
        build_portal_login_context(req, access, flash_error_code=flash_error_code),
    )
    return build_portal_page_response(html, cookie_header=flash_cookie_header)


@blueprint.function_name(name="portal_google_login_page")
@blueprint.route(
    route="portal/auth/google/login",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_google_login_page(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return build_portal_google_auth_start_response(req)
    except PortalGoogleAuthError as error:
        return build_portal_google_auth_error_response(req, error)


@blueprint.function_name(name="portal_google_callback_page")
@blueprint.route(
    route="portal/auth/google/callback",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_google_callback_page(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return build_portal_google_auth_callback_response(req)
    except PortalGoogleAuthError as error:
        return build_portal_google_auth_error_response(req, error)


@blueprint.function_name(name="portal_google_logout_page")
@blueprint.route(
    route="portal/auth/logout",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_google_logout_page(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return build_portal_google_logout_response(req)
    except PortalGoogleAuthError as error:
        return build_portal_google_auth_error_response(req, error)


@blueprint.function_name(name="portal_admin_events_create_api")
@blueprint.route(
    route="api/v1/admin/events",
    methods=["GET", "POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_events_create_api(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "GET":
        return portal_admin_events_list_api(req)

    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    idempotency_key = req.headers.get(PORTAL_API_IDEMPOTENCY_HEADER_NAME, "").strip()
    if not idempotency_key:
        return build_portal_api_error_response(
            400,
            "missing_idempotency_key",
            "缺少 Idempotency-Key。請重新整理管理平台後再試一次。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    event_payload, payload_error = parse_create_event_payload(payload)
    if event_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_event_payload",
            payload_error or "活動資料格式不合法。",
        )

    actor = get_portal_api_actor(access)
    event_id = build_event_id(idempotency_key, actor=actor)
    event_document = build_event_document(
        actor=actor,
        completion_hours=event_payload["completionHours"],
        document_types=event_payload["documentTypes"],
        event_end_date=event_payload["eventEndDate"],
        event_id=event_id,
        event_start_date=event_payload["eventStartDate"],
        name=event_payload["name"],
        status=event_payload["status"],
        completion_cert_download_starts_at=event_payload[
            "completionCertDownloadStartsAt"
        ],
        volunteer_service_ticket_names=event_payload["volunteerServiceTicketNames"] or [],
    )
    try:
        event, was_created = create_event_document(
            container=get_events_container(),
            event_document=event_document,
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"event": event},
        status_code=201 if was_created else 200,
    )


@blueprint.function_name(name="portal_admin_dashboard_welcome_metrics_api")
@blueprint.route(
    route="api/v1/admin/dashboard/welcome-metrics",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_dashboard_welcome_metrics_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    try:
        payload = build_portal_welcome_metrics_payload()
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "welcome_metrics_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(payload, status_code=200)


@blueprint.function_name(name="portal_admin_events_update_api")
@blueprint.route(
    route="api/v1/admin/events/{event_id}",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_events_update_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    event_id = str(req.route_params.get("event_id", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_event_id",
            "活動識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    event_payload, payload_error = parse_create_event_payload(payload)
    if event_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_event_payload",
            payload_error or "活動資料格式不合法。",
        )

    try:
        event = update_event_document(
            actor=get_portal_api_actor(access),
            completion_hours=event_payload["completionHours"],
            completion_cert_download_starts_at=event_payload[
                "completionCertDownloadStartsAt"
            ],
            container=get_events_container(),
            document_types=event_payload["documentTypes"],
            event_end_date=event_payload["eventEndDate"],
            event_id=event_id,
            event_start_date=event_payload["eventStartDate"],
            name=event_payload["name"],
            status=event_payload["status"],
            volunteer_service_ticket_names=event_payload["volunteerServiceTicketNames"],
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response({"event": event}, status_code=200)


@blueprint.function_name(name="portal_admin_event_volunteer_service_ticket_names_update_api")
@blueprint.route(
    route="api/v1/admin/events/{event_id}/volunteer-service-ticket-names",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_event_volunteer_service_ticket_names_update_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    event_id = str(req.route_params.get("event_id", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_event_id",
            "活動識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    if not isinstance(payload, dict) or not isinstance(payload.get("ticketNames"), list):
        return build_portal_api_error_response(
            400,
            "invalid_volunteer_service_ticket_names",
            "請提供志工服務證明支援票種清單。",
        )

    ticket_names = normalize_portal_volunteer_service_ticket_names(
        payload.get("ticketNames")
    )

    try:
        container = get_events_container()
        event = container.read_item(item=event_id, partition_key=event_id)
        if "volunteerServiceCert" not in normalize_portal_event_document_types(
            event.get("documentTypes")
        ):
            return build_portal_api_error_response(
                400,
                "volunteer_service_cert_not_enabled",
                "此活動未開放志工服務證明。",
            )
        updated_event = {
            **event,
            "volunteerServiceTicketNames": ticket_names,
            "updatedAt": utc_now_iso(),
            "updatedBy": get_portal_api_actor(access),
        }
        saved_event = container.replace_item(item=event_id, body=updated_event)
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            return build_portal_api_error_response(
                404,
                "event_not_found",
                "找不到指定活動。",
            )
        return build_portal_api_error_response(
            503,
            "event_store_unavailable",
            "活動資料暫時無法更新。",
        )

    return build_portal_api_json_response(
        {"event": normalize_portal_event_for_api(saved_event)},
        status_code=200,
    )


def portal_admin_events_list_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    try:
        payload = build_portal_events_json_payload()
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(payload, status_code=200)


@blueprint.function_name(name="portal_admin_completion_certs_list_api")
@blueprint.route(
    route="api/v1/admin/completion-certs",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_completion_certs_list_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    event_id = str(req.params.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_event_id",
            "活動識別碼不合法。",
        )

    try:
        documents = list_completion_cert_documents(
            container=get_completion_records_container(),
            event_id=event_id,
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {
            "completionCerts": [
                normalize_completion_cert_for_api(document)
                for document in documents
            ]
        },
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_completion_certs_import_api")
@blueprint.route(
    route="api/v1/admin/completion-certs/import",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_completion_certs_import_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    import_payload, payload_error, payload_error_details = parse_completion_csv_payload(payload)
    if import_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_completion_csv_payload",
            payload_error or "完訓證明 CSV 資料格式不合法。",
            details=payload_error_details,
        )

    event_id = import_payload["eventId"]
    try:
        read_portal_event(event_id)
        documents = build_completion_cert_documents_from_records(
            event_id=event_id,
            records=import_payload["records"],
        )
        saved_documents = upsert_completion_cert_documents(
            container=get_completion_records_container(),
            documents=documents,
        )
        current_documents = list_completion_cert_documents(
            container=get_completion_records_container(),
            event_id=event_id,
        )
        replace_event_completion_metrics(
            container=get_events_container(),
            event_id=event_id,
            metrics=summarize_completion_cert_documents(current_documents),
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定活動。" else 503,
            "event_not_found" if str(exc) == "找不到指定活動。" else "event_store_unavailable",
            str(exc),
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {
            "completionCerts": [
                normalize_completion_cert_for_api(document)
                for document in current_documents
            ],
            "summary": {"imported": len(saved_documents)},
        },
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_completion_certs_update_api")
@blueprint.route(
    route="api/v1/admin/completion-certs/{certid}",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_completion_certs_update_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    cert_id = str(req.route_params.get("certid", "")).strip()
    if not cert_id.startswith("ccert_"):
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_id",
            "完訓證明資料識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    update_payload, payload_error = parse_completion_cert_update_payload(payload)
    if update_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_payload",
            payload_error or "完訓證明資料格式不合法。",
        )

    event_id = update_payload["eventId"]
    try:
        container = get_completion_records_container()
        document = read_completion_cert_document(
            cert_id=cert_id,
            container=container,
            event_id=event_id,
        )
        if str(document.get("eventId", "")).strip() != event_id:
            return build_portal_api_error_response(
                404,
                "completion_cert_not_found",
                "找不到指定完訓證明資料。",
            )

        updates = update_payload["updates"]
        current_cert_status = str(document.get("certStatus", "")).strip() or "notIssued"
        if current_cert_status == "transferred":
            return build_portal_api_error_response(
                409,
                "completion_cert_already_transferred",
                "已轉移的完訓證明不可再修改資料。",
            )

        if current_cert_status == "issued" and PORTAL_COMPLETION_CERT_DATA_FIELDS.intersection(
            updates
        ):
            return build_portal_api_error_response(
                409,
                "completion_cert_already_issued",
                "已發行的完訓證明不可修改資料，請先撤銷發行狀態。",
            )

        if (
            updates.get("certStatus") == "notIssued"
            and current_cert_status not in {"issued", "notIssued"}
        ):
            return build_portal_api_error_response(
                409,
                "completion_cert_revoke_not_allowed",
                "只有已發行的完訓證明可撤銷發行狀態。",
            )

        updated_document = {**document, **updates}
        if updates.get("certStatus") == "notIssued":
            updated_document["issuedPdfBlobName"] = None
            updated_document["verificationTokenHash"] = None
            updated_document["issuedAt"] = None
            updated_document["certificateDisplayName"] = None
            updated_document["certificateDisplayOrganization"] = None
            updated_document["certificateNameDisplay"] = None
            updated_document["certificateLocale"] = None
        saved_document = replace_completion_cert_document(
            container=container,
            document=updated_document,
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定完訓證明資料。" else 503,
            "completion_cert_not_found"
            if str(exc) == "找不到指定完訓證明資料。"
            else "completion_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"completionCert": normalize_completion_cert_for_api(saved_document)},
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_volunteer_service_certs_list_api")
@blueprint.route(
    route="api/v1/admin/volunteer-service-certs",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_volunteer_service_certs_list_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    event_id = str(req.params.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_event_id",
            "活動識別碼不合法。",
        )

    try:
        event = read_portal_event(event_id)
        available_ticket_names = resolve_completion_ticket_names_for_event(event_id)
        documents = list_volunteer_service_cert_documents(
            container=get_volunteer_service_certs_container(),
            event_id=event_id,
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_unavailable",
            str(exc),
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定活動。" else 503,
            "event_not_found"
            if str(exc) == "找不到指定活動。"
            else "event_store_unavailable",
            str(exc),
        )
    except VolunteerServiceStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "volunteer_service_store_not_configured",
            str(exc),
        )
    except VolunteerServiceStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "volunteer_service_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {
            "settings": {
                "availableTicketNames": available_ticket_names,
                "supportedTicketNames": normalize_portal_volunteer_service_ticket_names(
                    event.get("volunteerServiceTicketNames")
                ),
            },
            "volunteerServiceCerts": [
                normalize_volunteer_service_cert_for_api(document)
                for document in documents
            ]
        },
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_volunteer_service_cert_update_api")
@blueprint.route(
    route="api/v1/admin/volunteer-service-certs/{certid}",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_volunteer_service_cert_update_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    cert_id = str(req.route_params.get("certid", "")).strip()
    if not cert_id.startswith("vscert_"):
        return build_portal_api_error_response(
            400,
            "invalid_volunteer_service_cert_id",
            "志工服務證明資料識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    if not isinstance(payload, dict):
        return build_portal_api_error_response(
            400,
            "invalid_volunteer_service_cert_payload",
            "請提供 JSON 物件。",
        )

    event_id = str(payload.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(400, "invalid_event_id", "活動識別碼不合法。")

    if "downloadEnabled" not in payload or not isinstance(payload.get("downloadEnabled"), bool):
        return build_portal_api_error_response(
            400,
            "invalid_download_enabled",
            "請提供可否下載的布林值。",
        )

    try:
        container = get_volunteer_service_certs_container()
        document = read_volunteer_service_cert_document(
            cert_id=cert_id,
            container=container,
            event_id=event_id,
        )
        saved_document = replace_volunteer_service_cert_document(
            container=container,
            document={
                **document,
                "downloadEnabled": payload["downloadEnabled"],
                "updatedAt": utc_now_iso(),
                "updatedBy": get_portal_api_actor(access),
            },
        )
    except VolunteerServiceStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "volunteer_service_store_not_configured",
            str(exc),
        )
    except VolunteerServiceStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定志工服務證明資料。" else 503,
            "volunteer_service_cert_not_found"
            if str(exc) == "找不到指定志工服務證明資料。"
            else "volunteer_service_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"volunteerServiceCert": normalize_volunteer_service_cert_for_api(saved_document)},
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_volunteer_service_cert_transfer_api")
@blueprint.route(
    route="api/v1/admin/volunteer-service-certs/transfers",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_volunteer_service_cert_transfer_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    if not isinstance(payload, dict):
        return build_portal_api_error_response(
            400,
            "invalid_transfer_payload",
            "請提供 JSON 物件。",
        )

    event_id = str(payload.get("eventId", "")).strip()
    completion_cert_id = str(payload.get("completionCertId", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(400, "invalid_event_id", "活動識別碼不合法。")
    if not completion_cert_id.startswith("ccert_"):
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_id",
            "完訓證明資料識別碼不合法。",
        )

    actor = get_portal_api_actor(access)
    transfer_timestamp = utc_now_iso()
    try:
        completion_container = get_completion_records_container()
        completion_document = read_completion_cert_document(
            cert_id=completion_cert_id,
            container=completion_container,
            event_id=event_id,
        )
        current_cert_status = str(completion_document.get("certStatus", "")).strip() or "notIssued"
        if current_cert_status == "issued":
            return build_portal_api_error_response(
                409,
                "completion_cert_already_issued",
                "已發行的完訓證明不可轉移文件類型，請先撤銷發行狀態。",
            )

        existing_transfer_type = str(
            completion_document.get("transferredToDocumentType", "")
        ).strip()
        if existing_transfer_type and existing_transfer_type != "volunteerServiceCert":
            return build_portal_api_error_response(
                409,
                "completion_cert_already_transferred",
                "此完訓證明資料已轉移到其他文件類型。",
            )

        volunteer_cert_id = build_volunteer_service_cert_id(
            completion_cert_id=completion_cert_id,
            event_id=event_id,
        )
        event_document = read_portal_event(event_id)
        volunteer_document = build_volunteer_service_cert_document(
            actor=actor,
            completion_cert=completion_document,
            event=event_document,
            now=transfer_timestamp,
            volunteer_service_cert_id=volunteer_cert_id,
        )
        saved_volunteer_document, _was_created = create_volunteer_service_cert_document(
            container=get_volunteer_service_certs_container(),
            document=volunteer_document,
        )
        updated_completion_document = {
            **completion_document,
            "certStatus": "transferred",
            "transferredToDocumentType": "volunteerServiceCert",
            "transferredToDocumentId": saved_volunteer_document["id"],
            "transferredAt": transfer_timestamp,
            "transferredBy": actor,
        }
        saved_completion_document = replace_completion_cert_document(
            container=completion_container,
            document=updated_completion_document,
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except VolunteerServiceStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "volunteer_service_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定完訓證明資料。" else 503,
            "completion_cert_not_found"
            if str(exc) == "找不到指定完訓證明資料。"
            else "volunteer_service_transfer_unavailable",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定活動。" else 503,
            "event_not_found"
            if str(exc) == "找不到指定活動。"
            else "event_store_unavailable",
            str(exc),
        )
    except VolunteerServiceStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "volunteer_service_transfer_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {
            "completionCert": normalize_completion_cert_for_api(saved_completion_document),
            "volunteerServiceCert": normalize_volunteer_service_cert_for_api(
                saved_volunteer_document
            ),
        },
        status_code=201,
    )


@blueprint.function_name(name="portal_admin_tax_receipts_list_create_api")
@blueprint.route(
    route="api/v1/admin/tax-receipts",
    methods=["GET", "POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_tax_receipts_list_create_api(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "GET":
        return portal_admin_tax_receipts_list_api(req)
    return portal_admin_tax_receipts_create_api(req)


def portal_admin_tax_receipts_list_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    event_id = str(req.params.get("eventId", "")).strip()
    if not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_event_id",
            "活動識別碼不合法。",
        )

    try:
        documents = list_tax_receipt_documents(
            container=get_tax_receipts_container(),
            event_id=event_id,
        )
    except TaxReceiptStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_not_configured",
            str(exc),
        )
    except TaxReceiptStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"taxReceipts": [normalize_tax_receipt_for_api(document) for document in documents]},
        status_code=200,
    )


def portal_admin_tax_receipts_create_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    idempotency_key = req.headers.get(PORTAL_API_IDEMPOTENCY_HEADER_NAME, "").strip()
    if not idempotency_key:
        return build_portal_api_error_response(
            400,
            "missing_idempotency_key",
            "缺少 Idempotency-Key。請重新整理管理平台後再試一次。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    receipt_payload, payload_error = parse_tax_receipt_payload(payload, require_file=True)
    if receipt_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_payload",
            payload_error or "繳稅證明資料格式不合法。",
        )

    event_id = receipt_payload["eventId"]
    actor = get_portal_api_actor(access)
    receipt_id = build_tax_receipt_id(
        idempotency_key,
        actor=actor,
        event_id=event_id,
    )
    file_payload = receipt_payload["file"]
    assert file_payload is not None
    source_blob_name = build_tax_receipt_blob_name(
        content_type=file_payload["contentType"],
        event_id=event_id,
        receipt_id=receipt_id,
    )

    try:
        ensure_event_supports_tax_receipt(event_id)
        container = get_tax_receipts_container()
        current_document = None
        try:
            current_document = read_tax_receipt_document(
                container=container,
                event_id=event_id,
                receipt_id=receipt_id,
            )
        except TaxReceiptStoreOperationError as exc:
            if str(exc) != "找不到指定繳稅證明資料。":
                raise
        if current_document is not None:
            file_sequence = resolve_existing_tax_receipt_file_sequence(
                container=container,
                current_document=current_document,
                event_id=event_id,
                receipt_id=receipt_id,
                tax_id=receipt_payload["taxId"],
            )
        else:
            file_sequence = resolve_next_tax_receipt_file_sequence(
                container=container,
                event_id=event_id,
                tax_id=receipt_payload["taxId"],
            )
        receipt_file_name = build_tax_receipt_file_name(
            content_type=file_payload["contentType"],
            file_sequence=file_sequence,
            tax_id=receipt_payload["taxId"],
        )
        upload_blob_bytes(
            blob_name=source_blob_name,
            container_name=get_tax_receipts_blob_container_name(),
            content_type=file_payload["contentType"],
            data=file_payload["bytes"],
        )
        document = build_tax_receipt_document(
            actor=actor,
            amount=receipt_payload["amount"],
            content_type=file_payload["contentType"],
            event_id=event_id,
            file_name=receipt_file_name,
            file_sequence=file_sequence,
            file_size=file_payload["fileSize"],
            generated_at=receipt_payload["generatedAt"],
            receipt_id=receipt_id,
            source_blob_name=source_blob_name,
            tax_id=receipt_payload["taxId"],
        )
        saved_document = upsert_tax_receipt_document(
            container=container,
            document=document,
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        status_code = 404 if str(exc) == "找不到指定活動。" else 400
        return build_portal_api_error_response(
            status_code,
            "event_not_found" if status_code == 404 else "event_not_open_for_tax_receipts",
            str(exc),
        )
    except (TaxReceiptStoreConfigurationError, BlobStoreConfigurationError) as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_not_configured",
            str(exc),
        )
    except (TaxReceiptStoreOperationError, BlobStoreOperationError) as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"taxReceipt": normalize_tax_receipt_for_api(saved_document)},
        status_code=201,
    )


@blueprint.function_name(name="portal_admin_tax_receipts_update_delete_api")
@blueprint.route(
    route="api/v1/admin/tax-receipts/{receiptid}",
    methods=["PUT", "DELETE"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_tax_receipts_update_delete_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    if req.method == "DELETE":
        return portal_admin_tax_receipts_delete_api(req)
    return portal_admin_tax_receipts_update_api(req)


def portal_admin_tax_receipts_update_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    receipt_id = str(req.route_params.get("receiptid", "")).strip()
    if not receipt_id.startswith("trec_"):
        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_id",
            "繳稅證明資料識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    receipt_payload, payload_error = parse_tax_receipt_payload(payload, require_file=False)
    if receipt_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_payload",
            payload_error or "繳稅證明資料格式不合法。",
        )

    event_id = receipt_payload["eventId"]
    actor = get_portal_api_actor(access)
    try:
        ensure_event_supports_tax_receipt(event_id)
        container = get_tax_receipts_container()
        document = read_tax_receipt_document(
            container=container,
            event_id=event_id,
            receipt_id=receipt_id,
        )
        existing_tax_id = str(document.get("taxId", "")).strip()
        if receipt_payload["taxId"] != existing_tax_id:
            return build_portal_api_error_response(
                400,
                "tax_receipt_tax_id_immutable",
                "統編不可在編輯時修改。請刪除後重新新增。",
            )
        updated_document = {
            **document,
            "amount": receipt_payload["amount"],
            "generatedAt": receipt_payload["generatedAt"],
            "taxId": receipt_payload["taxId"],
            "updatedBy": actor,
            "updatedAt": utc_now_iso(),
        }
        file_sequence = resolve_existing_tax_receipt_file_sequence(
            container=container,
            current_document=document,
            event_id=event_id,
            receipt_id=receipt_id,
            tax_id=receipt_payload["taxId"],
        )
        updated_document["fileSequence"] = file_sequence
        file_payload = receipt_payload["file"]
        receipt_content_type = str(document.get("contentType", "")).strip()
        if file_payload is not None:
            receipt_content_type = file_payload["contentType"]
        updated_document["fileName"] = build_tax_receipt_file_name(
            content_type=receipt_content_type,
            file_sequence=file_sequence,
            tax_id=receipt_payload["taxId"],
        )
        if file_payload is not None:
            source_blob_name = build_tax_receipt_blob_name(
                content_type=file_payload["contentType"],
                event_id=event_id,
                receipt_id=receipt_id,
            )
            upload_blob_bytes(
                blob_name=source_blob_name,
                container_name=get_tax_receipts_blob_container_name(),
                content_type=file_payload["contentType"],
                data=file_payload["bytes"],
            )
            updated_document.update(
                {
                    "contentType": file_payload["contentType"],
                    "fileSize": file_payload["fileSize"],
                    "sourceBlobName": source_blob_name,
                }
            )
        saved_document = replace_tax_receipt_document(
            container=container,
            document=updated_document,
        )
    except EventStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        status_code = 404 if str(exc) == "找不到指定活動。" else 400
        return build_portal_api_error_response(
            status_code,
            "event_not_found" if status_code == 404 else "event_not_open_for_tax_receipts",
            str(exc),
        )
    except (TaxReceiptStoreConfigurationError, BlobStoreConfigurationError) as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_not_configured",
            str(exc),
        )
    except TaxReceiptStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定繳稅證明資料。" else 503,
            "tax_receipt_not_found"
            if str(exc) == "找不到指定繳稅證明資料。"
            else "tax_receipt_store_unavailable",
            str(exc),
        )
    except BlobStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"taxReceipt": normalize_tax_receipt_for_api(saved_document)},
        status_code=200,
    )


def portal_admin_tax_receipts_delete_api(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    receipt_id = str(req.route_params.get("receiptid", "")).strip()
    event_id = str(req.params.get("eventId", "")).strip()
    if not receipt_id.startswith("trec_") or not event_id.startswith("evt_"):
        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_id",
            "繳稅證明資料識別碼不合法。",
        )

    try:
        container = get_tax_receipts_container()
        document = read_tax_receipt_document(
            container=container,
            event_id=event_id,
            receipt_id=receipt_id,
        )
        delete_tax_receipt_document(
            container=container,
            event_id=event_id,
            receipt_id=receipt_id,
        )
        blob_name = str(document.get("sourceBlobName", "")).strip()
        if blob_name:
            delete_blob(
                blob_name=blob_name,
                container_name=get_tax_receipts_blob_container_name(),
            )
    except (TaxReceiptStoreConfigurationError, BlobStoreConfigurationError) as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_not_configured",
            str(exc),
        )
    except TaxReceiptStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定繳稅證明資料。" else 503,
            "tax_receipt_not_found"
            if str(exc) == "找不到指定繳稅證明資料。"
            else "tax_receipt_store_unavailable",
            str(exc),
        )
    except BlobStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response({"deleted": True}, status_code=200)


@blueprint.function_name(name="public_tax_receipts_download_api")
@blueprint.route(
    route="api/v1/tax-receipts/download",
    methods=["POST"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_tax_receipts_download_api(req: func.HttpRequest) -> func.HttpResponse:
    client_ip = resolve_public_download_client_ip(req)
    attempt_id = build_public_lookup_attempt_id(client_ip) if client_ip else None
    if attempt_id is not None and is_public_lookup_blocked_by_local_cache(attempt_id=attempt_id):
        return build_tax_receipt_download_blocked_response(
            read_public_lookup_cached_attempt_document(attempt_id=attempt_id)
        )

    attempt_document = (
        read_public_download_attempt_document(attempt_id=attempt_id)
        if attempt_id is not None
        else None
    )
    if is_public_lookup_blocked(attempt_document=attempt_document):
        remember_public_lookup_block(
            attempt_id=attempt_id,
            attempt_document=attempt_document or {},
        )
        return build_tax_receipt_download_blocked_response(attempt_document)

    try:
        payload = req.get_json()
    except ValueError:
        updated_attempt_document = record_public_download_failure(
            attempt_id=attempt_id,
            attempt_document=attempt_document,
            client_ip=client_ip,
        )
        if is_public_lookup_blocked(attempt_document=updated_attempt_document):
            return build_tax_receipt_download_blocked_response(updated_attempt_document)

        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_download_payload",
            "請提供 JSON 物件。",
        )

    if not isinstance(payload, dict):
        updated_attempt_document = record_public_download_failure(
            attempt_id=attempt_id,
            attempt_document=attempt_document,
            client_ip=client_ip,
        )
        if is_public_lookup_blocked(attempt_document=updated_attempt_document):
            return build_tax_receipt_download_blocked_response(updated_attempt_document)

        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_download_payload",
            "請提供 JSON 物件。",
        )

    event_id = str(payload.get("eventId", "")).strip()
    receipt_ids = parse_tax_receipt_download_receipt_ids(payload.get("receiptIds"))
    ticket = str(payload.get("downloadTicket", "")).strip()
    is_portal_download = is_portal_tax_receipt_download_request(req)
    if not is_authorized_tax_receipt_download_request(
        req,
        event_id=event_id,
        receipt_ids=receipt_ids,
        ticket=ticket,
    ):
        updated_attempt_document = record_public_download_failure(
            attempt_id=attempt_id,
            attempt_document=attempt_document,
            client_ip=client_ip,
        )
        if is_public_lookup_blocked(attempt_document=updated_attempt_document):
            return build_tax_receipt_download_blocked_response(updated_attempt_document)

        return build_portal_api_error_response(
            403,
            "invalid_tax_receipt_download_authorization",
            "下載資格已失效，請重新查詢後再下載。",
        )

    ticket_payload = (
        read_tax_receipt_download_ticket_payload(
            ticket=ticket,
            event_id=event_id,
            receipt_ids=receipt_ids,
        )
        if not is_portal_download and ticket
        else None
    )
    response = build_tax_receipts_download_response(
        event_id=event_id,
        is_portal_download=is_portal_download,
        public_download_subject_key=str((ticket_payload or {}).get("subjectKey", "")).strip(),
        receipt_ids=receipt_ids,
    )
    if not is_portal_download and response.status_code < 400:
        record_public_download_success(attempt_id=attempt_id, client_ip=client_ip)

    return response


def parse_tax_receipt_download_receipt_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    receipt_ids: list[str] = []
    for item in value:
        receipt_id = str(item).strip()
        if receipt_id and receipt_id not in receipt_ids:
            receipt_ids.append(receipt_id)
    return receipt_ids


def build_tax_receipts_download_response(
    *,
    event_id: str,
    is_portal_download: bool,
    public_download_subject_key: str = "",
    receipt_ids: list[str],
) -> func.HttpResponse:
    if (
        not event_id.startswith("evt_")
        or not receipt_ids
        or any(not receipt_id.startswith("trec_") for receipt_id in receipt_ids)
    ):
        return build_portal_api_error_response(
            400,
            "invalid_tax_receipt_id",
            "繳稅證明資料識別碼不合法。",
        )

    try:
        documents: list[dict[str, Any]] = []
        file_payloads: list[tuple[dict[str, Any], bytes]] = []
        document = read_tax_receipt_document(
            container=get_tax_receipts_container(),
            event_id=event_id,
            receipt_id=receipt_ids[0],
        )
        documents.append(document)
        for receipt_id in receipt_ids[1:]:
            documents.append(
                read_tax_receipt_document(
                    container=get_tax_receipts_container(),
                    event_id=event_id,
                    receipt_id=receipt_id,
                )
            )
        if not is_portal_download:
            blocked_documents = list_public_tax_receipt_documents_in_cooldown(
                documents,
                public_download_subject_key=public_download_subject_key,
            )
            if len(blocked_documents) == len(documents):
                return build_public_tax_receipt_download_cooldown_response(blocked_documents)

        blob_container_name = get_tax_receipts_blob_container_name()
        for document in documents:
            file_payloads.append(
                (
                    document,
                    download_blob_bytes(
                        blob_name=str(document.get("sourceBlobName", "")).strip(),
                        container_name=blob_container_name,
                    ),
                )
            )
        record_tax_receipt_downloads(
            documents,
            is_portal_download=is_portal_download,
            public_download_subject_key=public_download_subject_key,
        )
    except (TaxReceiptStoreConfigurationError, BlobStoreConfigurationError) as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_not_configured",
            str(exc),
        )
    except TaxReceiptStoreOperationError as exc:
        return build_portal_api_error_response(
            404 if str(exc) == "找不到指定繳稅證明資料。" else 503,
            "tax_receipt_not_found"
            if str(exc) == "找不到指定繳稅證明資料。"
            else "tax_receipt_store_unavailable",
            str(exc),
        )
    except BlobStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "tax_receipt_store_unavailable",
            str(exc),
        )

    if len(file_payloads) == 1:
        document, blob_bytes = file_payloads[0]
        return build_tax_receipt_file_http_response(document=document, blob_bytes=blob_bytes)

    return build_tax_receipts_zip_response(event_id=event_id, file_payloads=file_payloads)


def list_public_tax_receipt_documents_in_cooldown(
    documents: list[dict[str, Any]],
    *,
    public_download_subject_key: str,
) -> list[dict[str, Any]]:
    if not public_download_subject_key:
        return []

    blocked_documents: list[dict[str, Any]] = []
    for document in documents:
        if is_public_tax_receipt_download_in_cooldown(
            document,
            public_download_subject_key=public_download_subject_key,
        ):
            blocked_documents.append(document)

    return blocked_documents


def is_public_tax_receipt_download_in_cooldown(
    document: dict[str, Any],
    *,
    public_download_subject_key: str,
) -> bool:
    if str(document.get("lastDownloadSubjectKey", "")).strip() != public_download_subject_key:
        return False

    last_download_at = parse_utc_iso_datetime(str(document.get("lastDownloadAt", "")).strip())
    if last_download_at is None:
        return False

    cooldown_seconds = read_public_tax_receipt_download_cooldown_seconds()
    if cooldown_seconds <= 0:
        return False

    return last_download_at + timedelta(seconds=cooldown_seconds) > utc_now_iso_datetime()


def build_public_tax_receipt_download_cooldown_response(
    blocked_documents: list[dict[str, Any]],
) -> func.HttpResponse:
    return build_portal_api_error_response(
        429,
        "tax_receipt_download_cooldown",
        "這份收據剛剛已下載，請稍後再試，或改選其他尚未下載的檔案。",
        details={
            "blockedReceiptIds": [
                str(document.get("id", "")).strip()
                for document in blocked_documents
                if str(document.get("id", "")).strip()
            ],
        },
    )


def read_public_tax_receipt_download_cooldown_seconds() -> int:
    raw_value = os.getenv("TAX_RECEIPT_PUBLIC_DOWNLOAD_COOLDOWN_SECONDS", "").strip()
    if raw_value.isdecimal():
        return max(0, int(raw_value))

    return PUBLIC_TAX_RECEIPT_DOWNLOAD_COOLDOWN_SECONDS


def utc_now_iso_datetime() -> Any:
    parsed_now = parse_utc_iso_datetime(utc_now_iso())
    if parsed_now is None:
        raise ValueError("utc_now_iso returned an invalid timestamp")
    return parsed_now


def record_tax_receipt_downloads(
    documents: list[dict[str, Any]],
    *,
    is_portal_download: bool,
    public_download_subject_key: str = "",
) -> None:
    timestamp = utc_now_iso()
    try:
        container = get_tax_receipts_container()
        for document in documents:
            receipt_id = str(document.get("id", "")).strip()
            event_id = str(document.get("eventId", "")).strip()
            if not receipt_id or not event_id:
                continue

            updated_document = {
                **document,
            }
            if is_portal_download:
                updated_document["portalDownloadCount"] = (
                    read_non_negative_int_field(
                        document,
                        ("portalDownloadCount",),
                    )
                    + 1
                )
                updated_document["lastPortalDownloadAt"] = timestamp
            else:
                updated_document["downloadCount"] = (
                    read_non_negative_int_field(
                        document,
                        ("downloadCount",),
                    )
                    + 1
                )
                updated_document["lastDownloadAt"] = timestamp
                if public_download_subject_key:
                    updated_document["lastDownloadSubjectKey"] = public_download_subject_key
            replace_tax_receipt_document(
                container=container,
                document=updated_document,
            )
            document.update(updated_document)
    except (TaxReceiptStoreConfigurationError, TaxReceiptStoreOperationError):
        LOGGER.warning("Unable to record tax receipt download metadata.", exc_info=True)


def build_tax_receipt_file_http_response(
    *,
    document: dict[str, Any],
    blob_bytes: bytes,
) -> func.HttpResponse:
    receipt_id = str(document.get("id", "")).strip()
    file_name = str(document.get("fileName", "")).strip() or f"{receipt_id}.pdf"
    download_file_name = sanitize_tax_receipt_download_file_name(file_name)
    return func.HttpResponse(
        body=blob_bytes,
        status_code=200,
        mimetype=str(document.get("contentType", "")).strip() or "application/octet-stream",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": f'attachment; filename="{download_file_name}"',
        },
    )


def build_tax_receipts_zip_response(
    *,
    event_id: str,
    file_payloads: list[tuple[dict[str, Any], bytes]],
) -> func.HttpResponse:
    zip_buffer = io.BytesIO()
    used_file_names: set[str] = set()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for document, blob_bytes in file_payloads:
            receipt_id = str(document.get("id", "")).strip()
            file_name = str(document.get("fileName", "")).strip() or f"{receipt_id}.pdf"
            zip_file.writestr(
                uniquify_tax_receipt_zip_file_name(
                    sanitize_tax_receipt_download_file_name(file_name),
                    used_file_names,
                ),
                blob_bytes,
            )

    return func.HttpResponse(
        body=zip_buffer.getvalue(),
        status_code=200,
        mimetype="application/zip",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="tax-receipts.zip"',
        },
    )


def sanitize_tax_receipt_download_file_name(file_name: str) -> str:
    return file_name.replace("\\", "_").replace('"', "'").replace("\r", "").replace("\n", "")


def uniquify_tax_receipt_zip_file_name(file_name: str, used_file_names: set[str]) -> str:
    if file_name not in used_file_names:
        used_file_names.add(file_name)
        return file_name

    stem, dot, suffix = file_name.rpartition(".")
    base_name = stem if dot else file_name
    extension = f".{suffix}" if dot else ""
    index = 2
    while True:
        candidate = f"{base_name}-{index}{extension}"
        if candidate not in used_file_names:
            used_file_names.add(candidate)
            return candidate
        index += 1


@blueprint.function_name(name="portal_admin_completion_cert_change_requests_list_api")
@blueprint.route(
    route="api/v1/admin/completion-cert-change-requests",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_completion_cert_change_requests_list_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_read_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    status = str(req.params.get("status", "pending")).strip() or "pending"
    if status not in {
        "pending",
        "completed",
        "cancelledByIssue",
        *PORTAL_COMPLETION_CERT_REQUEST_ALLOWED_REVIEW_STATUSES,
    }:
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_request_status",
            "修改申請狀態不合法。",
        )

    try:
        requests_container = get_completion_cert_requests_container()
        certs_container = get_completion_records_container()
        request_documents = list_completion_cert_request_documents(
            container=requests_container,
            status=status,
        )
        normalized_requests = []
        for request_document in request_documents:
            completion_cert = None
            completion_cert_id = str(
                request_document.get("completionCertId", "")
            ).strip()
            event_id = str(request_document.get("eventId", "")).strip()
            if completion_cert_id and event_id:
                try:
                    completion_cert = read_completion_cert_document(
                        cert_id=completion_cert_id,
                        container=certs_container,
                        event_id=event_id,
                    )
                except CompletionStoreOperationError:
                    completion_cert = None
            normalized_requests.append(
                normalize_completion_cert_request_for_api(
                    request_document,
                    completion_cert=completion_cert,
                )
            )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {"changeRequests": normalized_requests},
        status_code=200,
    )


@blueprint.function_name(name="portal_admin_completion_cert_change_requests_review_api")
@blueprint.route(
    route="api/v1/admin/completion-cert-change-requests/{requestid}",
    methods=["PUT"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_admin_completion_cert_change_requests_review_api(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_api_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    request_id = str(req.route_params.get("requestid", "")).strip()
    if not request_id.startswith("ccreq_"):
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_request_id",
            "完訓證明修改申請識別碼不合法。",
        )

    try:
        payload = req.get_json()
    except ValueError:
        return build_portal_api_error_response(400, "invalid_json", "請提供合法 JSON。")

    review_payload, payload_error = parse_completion_cert_request_review_payload(payload)
    if review_payload is None:
        return build_portal_api_error_response(
            400,
            "invalid_completion_cert_request_payload",
            payload_error or "完訓證明修改申請審核資料格式不合法。",
        )

    event_id = review_payload["eventId"]
    try:
        requests_container = get_completion_cert_requests_container()
        certs_container = get_completion_records_container()
        request_document = read_completion_cert_request_document(
            container=requests_container,
            event_id=event_id,
            request_id=request_id,
        )
        if str(request_document.get("status", "")).strip() != "pending":
            return build_portal_api_error_response(
                409,
                "completion_cert_request_already_reviewed",
                "此修改申請已完成審核。",
            )

        completion_cert_id = str(request_document.get("completionCertId", "")).strip()
        cert_document = read_completion_cert_document(
            cert_id=completion_cert_id,
            container=certs_container,
            event_id=event_id,
        )
        reviewed_at = utc_now_iso()
        updated_cert_document = {
            **cert_document,
            **review_payload["updates"],
            "certStatus": "notIssued",
            "updatedAt": reviewed_at,
        }
        saved_cert_document = replace_completion_cert_document(
            container=certs_container,
            document=updated_cert_document,
        )

        updated_request_document = {
            **request_document,
            "status": review_payload["status"],
            "reviewedBy": get_portal_api_actor(access),
            "reviewedAt": reviewed_at,
            "reviewNote": review_payload["reviewNote"] or None,
            "updatedAt": reviewed_at,
        }
        saved_request_document = replace_completion_cert_request_document(
            container=requests_container,
            document=updated_request_document,
        )
    except CompletionStoreConfigurationError as exc:
        return build_portal_api_error_response(
            503,
            "completion_store_not_configured",
            str(exc),
        )
    except CompletionStoreOperationError as exc:
        not_found = str(exc) in {
            "找不到指定完訓證明修改申請。",
            "找不到指定完訓證明資料。",
        }
        return build_portal_api_error_response(
            404 if not_found else 503,
            "completion_cert_request_not_found"
            if not_found
            else "completion_store_unavailable",
            str(exc),
        )

    return build_portal_api_json_response(
        {
            "changeRequest": normalize_completion_cert_request_for_api(
                saved_request_document,
                completion_cert=saved_cert_document,
            )
        },
        status_code=200,
    )


@blueprint.function_name(name="portal_dashboard_page")
@blueprint.route(
    route="portal/dashboard",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_page(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    schedule_portal_event_store_prewarm()

    html = render_html_template(
        load_portal_dashboard_template(),
        build_portal_dashboard_context(req, access),
    )
    return build_portal_page_response(html)


@blueprint.function_name(name="portal_dashboard_welcome_page")
@blueprint.route(
    route="portal/dashboard/welcome",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_welcome_page(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    html = render_html_template(
        load_portal_dashboard_welcome_template(),
        build_portal_dashboard_welcome_context(req, access),
    )
    return build_portal_page_response(html)


@blueprint.function_name(name="portal_dashboard_completion_certs_page")
@blueprint.route(
    route="portal/dashboard/completion-certs",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_completion_certs_page(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(
        render_html_template(
            load_portal_dashboard_completion_certs_template(),
            build_portal_dashboard_context(req, access),
        )
    )


@blueprint.function_name(name="portal_dashboard_completion_reviews_page")
@blueprint.route(
    route="portal/dashboard/completion-reviews",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_completion_reviews_page(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(
        render_html_template(
            load_portal_dashboard_completion_reviews_template(),
            build_portal_dashboard_context(req, access),
        )
    )


@blueprint.function_name(name="portal_dashboard_volunteer_service_certs_page")
@blueprint.route(
    route="portal/dashboard/volunteer-service-certs",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_volunteer_service_certs_page(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(
        render_html_template(
            load_portal_dashboard_volunteer_service_certs_template(),
            build_portal_dashboard_context(req, access),
        )
    )


@blueprint.function_name(name="portal_dashboard_tax_receipts_page")
@blueprint.route(
    route="portal/dashboard/tax-receipts",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_tax_receipts_page(
    req: func.HttpRequest,
) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(
        render_html_template(
            load_portal_dashboard_tax_receipts_template(),
            build_portal_dashboard_context(req, access),
        )
    )


@blueprint.function_name(name="portal_dashboard_events_page")
@blueprint.route(
    route="portal/dashboard/events",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_events_page(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    html = render_html_template(
        load_portal_dashboard_events_template(),
        build_portal_dashboard_events_context(req, access),
    )
    return build_portal_page_response(html)
