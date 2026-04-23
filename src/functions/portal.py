from __future__ import annotations

from functools import lru_cache
from html import escape
from pathlib import Path

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
    is_running_in_azure_environment,
    resolve_portal_access,
)
from src.shared.templates import render_html_template

blueprint = func.Blueprint()

PORTAL_ENTRY_PATH = "/portal"
PORTAL_DASHBOARD_PATH = "/portal/dashboard"
PORTAL_HOME_PATH = "/"
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


def build_portal_page_response(body: str) -> func.HttpResponse:
    return func.HttpResponse(
        body=body,
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers={
            "Content-Language": "zh-TW",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


def build_portal_redirect_response(location: str) -> func.HttpResponse:
    return func.HttpResponse(
        body="",
        status_code=302,
        headers={
            "Cache-Control": "no-store",
            "Location": location,
        },
    )


def build_portal_home_link_html() -> str:
    return (
        f'<a class="secondary-button portal-action-link" href="{PORTAL_HOME_PATH}" '
        'data-loading-label="返回首頁中...">'
        "返回首頁"
        "</a>"
    )


def build_portal_login_context(req: func.HttpRequest, access: PortalAccess) -> dict[str, str]:
    login_url = build_portal_login_url(req, PORTAL_ENTRY_PATH)
    logout_url = build_portal_logout_url(req, PORTAL_ENTRY_PATH)
    home_link_html = build_portal_home_link_html()
    lead_html = ""
    feedback_html = ""
    portal_google_auth_configured = is_portal_google_auth_configured()
    azure_environment = is_running_in_azure_environment()

    if access.principal.is_authenticated:
        email_summary = access.principal.email or "未提供電子郵件 claim"
        identity_html = (
            '<div class="portal-identity-card">'
            '<span class="portal-identity-label">目前登入帳號</span>'
            f'<strong class="portal-identity-value">{escape(access.principal.display_name)}</strong>'
            f'<span class="portal-identity-meta">{escape(email_summary)}</span>'
            "</div>"
        )
    else:
        identity_html = ""

    if not access.principal.is_authenticated:
        if not portal_google_auth_configured and not azure_environment:
            feedback_html = (
                '<div class="form-feedback is-error" id="form-feedback" role="status" aria-live="polite">'
                "本機 Google 登入尚未設定完成。請先在 local.settings.json 設定 "
                "PORTAL_GOOGLE_CLIENT_ID 與 PORTAL_GOOGLE_CLIENT_SECRET，"
                "再重新啟動 Azure Functions。"
                "</div>"
            )
            primary_action_html = (
                '<button class="submit-button" type="button" disabled aria-disabled="true">'
                "Google 登入尚未設定"
                "</button>"
            )
            secondary_action_html = (
                '<p class="portal-auth-note">'
                "redirect URI 應設為 http://localhost:7075/portal/auth/google/callback。"
                "</p>"
                f"{home_link_html}"
            )
            return {
                "portal_panel_kicker": "管理者登入",
                "portal_lead_html": lead_html,
                "portal_feedback_html": feedback_html,
                "portal_identity_html": identity_html,
                "portal_primary_action_html": primary_action_html,
                "portal_secondary_action_html": secondary_action_html,
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
            "portal_lead_html": lead_html,
            "portal_feedback_html": feedback_html,
            "portal_identity_html": identity_html,
            "portal_primary_action_html": primary_action_html,
            "portal_secondary_action_html": home_link_html,
        }

    primary_action_html = (
        f'<a class="submit-button portal-action-link" href="{escape(logout_url)}" '
        'data-loading-label="登出中...">'
        "切換帳號"
        "</a>"
    )
    lead_html = (
        '<p class="portal-auth-lead">'
        "目前登入的帳號缺少可用的電子郵件資訊，因此無法進入管理平台。"
        "</p>"
    )
    feedback_message = "請切換到其他 Google 帳號，或確認這個帳號已提供可驗證的 email 後再試一次。"
    secondary_message = "管理平台登入目前仍需要可用的 email claim。"
    feedback_html = (
        '<div class="form-feedback is-error" id="form-feedback" role="status" aria-live="polite">'
        f"{feedback_message}"
        "</div>"
    )
    return {
        "portal_panel_kicker": "權限不足",
        "portal_lead_html": lead_html,
        "portal_feedback_html": feedback_html,
        "portal_identity_html": identity_html,
        "portal_primary_action_html": primary_action_html,
        "portal_secondary_action_html": (
            '<p class="portal-auth-note">'
            f"{secondary_message}"
            "</p>"
            f"{home_link_html}"
        ),
    }


def build_portal_dashboard_context(req: func.HttpRequest, access: PortalAccess) -> dict[str, str]:
    return {
        "portal_entry_path": PORTAL_ENTRY_PATH,
        "portal_logout_url": build_portal_logout_url(req, PORTAL_ENTRY_PATH),
        "portal_user_display_name": access.principal.display_name,
    }


def build_portal_google_auth_error_response(error: PortalGoogleAuthError) -> func.HttpResponse:
    return func.HttpResponse(
        body=f"Google 登入失敗：{error}",
        status_code=error.status_code,
        mimetype="text/plain",
        charset="utf-8",
        headers={
            "Cache-Control": "no-store",
        },
    )


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
    access = resolve_portal_access(req)
    if access.is_authorized:
        return build_portal_redirect_response(PORTAL_DASHBOARD_PATH)

    html = render_html_template(
        load_portal_login_template(),
        build_portal_login_context(req, access),
    )
    return build_portal_page_response(html)


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
        return build_portal_google_auth_error_response(error)


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
        return build_portal_google_auth_error_response(error)


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
        return build_portal_google_auth_error_response(error)


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
