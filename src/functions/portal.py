from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache
from html import escape
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import azure.functions as func

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
from src.shared.event_store import (
    EventStoreConfigurationError,
    EventStoreOperationError,
    build_event_document,
    build_event_id,
    create_event_document,
    get_events_container,
    list_event_documents,
    update_event_document,
)
from src.shared.page_alerts import (
    DEFAULT_PAGE_ALERT_CONTEXT,
    build_page_alert_html,
    resolve_page_alert_dismiss_delay_ms,
)
from src.shared.templates import render_html_template

blueprint = func.Blueprint()

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
PORTAL_ALLOWED_EVENT_DOCUMENT_TYPES = frozenset({"completionCert", "taxReceipt"})
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
portal_event_store_prewarm_future: Future[object] | None = None


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
            '<img class="portal-sso-button-icon" src="/assets/google-g-icon.svg" alt="" aria-hidden="true">'
            '<span class="portal-sso-button-copy">'
            '<span class="portal-sso-button-label">使用 Google 繼續</span>'
            "</span>"
            "</a>"
        )
        return {
            "portal_panel_kicker": "管理者登入",
            "page_alert_html": page_alert_html,
            "portal_lead_html": lead_html,
            "portal_feedback_html": feedback_html,
            "portal_identity_html": identity_html,
            "portal_primary_action_html": primary_action_html,
            "portal_secondary_action_html": home_link_html,
        }

    return {
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
    global portal_event_store_prewarm_future

    if (
        portal_event_store_prewarm_future is not None
        and not portal_event_store_prewarm_future.done()
    ):
        return

    portal_event_store_prewarm_future = PORTAL_EVENT_STORE_PREWARM_EXECUTOR.submit(
        get_events_container
    )


def build_portal_events_json_payload() -> dict[str, Any]:
    try:
        events = list_event_documents(container=get_events_container())
    except (EventStoreConfigurationError, EventStoreOperationError) as exc:
        raise EventStoreOperationError(str(exc)) from exc

    return {"events": [normalize_portal_event_for_api(event) for event in events]}


def normalize_portal_event_for_api(event: dict[str, Any]) -> dict[str, Any]:
    event_status = str(event.get("status", "")).strip()
    return {
        "id": str(event.get("id", "")).strip(),
        "name": str(event.get("name", "")).strip(),
        "status": event_status if event_status in PORTAL_ALLOWED_EVENT_STATUSES else "unlisted",
        "documentTypes": normalize_portal_event_document_types(event.get("documentTypes")),
        "completionCertDownloadStartsAt": str(
            event.get("completionCertDownloadStartsAt") or ""
        ).strip(),
    }


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
) -> func.HttpResponse:
    return build_portal_api_json_response(
        {"error": {"code": code, "message": message}},
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
    if "completionCert" in document_types:
        if parse_utc_iso_datetime(completion_starts_at) is None:
            return None, "完訓證明開放下載時間必須使用 UTC ISO 8601 格式。"
    else:
        completion_starts_at = ""

    return (
        {
            "name": name,
            "status": status,
            "documentTypes": document_types,
            "completionCertDownloadStartsAt": completion_starts_at or None,
        },
        None,
    )


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
        document_types=event_payload["documentTypes"],
        event_id=event_id,
        name=event_payload["name"],
        status=event_payload["status"],
        completion_cert_download_starts_at=event_payload[
            "completionCertDownloadStartsAt"
        ],
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
            completion_cert_download_starts_at=event_payload[
                "completionCertDownloadStartsAt"
            ],
            container=get_events_container(),
            document_types=event_payload["documentTypes"],
            event_id=event_id,
            name=event_payload["name"],
            status=event_payload["status"],
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
        build_portal_dashboard_context(req, access),
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
        load_portal_dashboard_completion_certs_template()
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
        load_portal_dashboard_tax_receipts_template()
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
