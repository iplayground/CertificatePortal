from __future__ import annotations

from functools import lru_cache
from html import escape
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

import azure.functions as func

from src.shared.portal_auth import (
    PortalGoogleAuthError,
    PortalAccess,
    build_portal_google_auth_callback_response,
    build_portal_google_auth_start_response,
    build_portal_google_logout_response,
    build_portal_login_url,
    build_portal_logout_url,
    is_portal_google_auth_configured,
    is_portal_google_group_auth_configured,
    resolve_portal_access,
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
PORTAL_LOGIN_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_login.html"
PORTAL_DASHBOARD_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_dashboard.html"
PORTAL_DASHBOARD_WELCOME_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_welcome.html"
)
PORTAL_DASHBOARD_RECORDS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_records.html"
)
PORTAL_DASHBOARD_UPLOAD_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_upload.html"
)


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
def load_portal_dashboard_records_template() -> str:
    return PORTAL_DASHBOARD_RECORDS_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_upload_template() -> str:
    return PORTAL_DASHBOARD_UPLOAD_TEMPLATE_PATH.read_text(encoding="utf-8")


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
        "portal_user_display_name": access.principal.display_name,
    }


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


@blueprint.function_name(name="portal_dashboard_records_page")
@blueprint.route(
    route="portal/dashboard/records",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_records_page(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(load_portal_dashboard_records_template())


@blueprint.function_name(name="portal_dashboard_upload_page")
@blueprint.route(
    route="portal/dashboard/upload",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_upload_page(req: func.HttpRequest) -> func.HttpResponse:
    access = require_portal_access(req)
    if isinstance(access, func.HttpResponse):
        return access

    return build_portal_page_response(load_portal_dashboard_upload_template())
