from __future__ import annotations

from http.cookies import SimpleCookie

import azure.functions as func
import pytest

from src.functions.assets import static_asset
from src.functions.portal import (
    PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR,
    portal_dashboard_completion_certs_page,
    portal_dashboard_events_page,
    portal_dashboard_page,
    portal_dashboard_tax_receipts_page,
    portal_dashboard_welcome_page,
    portal_google_callback_page,
    portal_google_login_page,
    portal_google_logout_page,
    portal_login_page,
    resolve_portal_login_alert_dismiss_delay_ms,
)
from src.shared.portal_google_group_auth import PortalGoogleGroupAuthorizationError


def build_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    route_params: dict[str, str] | None = None,
) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url=url,
        headers=headers or {},
        params=params or {},
        route_params=route_params or {},
        body=b"",
    )


def configure_portal_auth_bypass_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    display_name: str = "王小明",
    email: str | None = "admin@iplayground.io",
) -> None:
    monkeypatch.setenv("PORTAL_AUTH_BYPASS_ENABLED", "true")
    monkeypatch.setenv("PORTAL_AUTH_BYPASS_DISPLAY_NAME", display_name)
    if email is None:
        monkeypatch.setenv("PORTAL_AUTH_BYPASS_EMAIL", "")
    else:
        monkeypatch.setenv("PORTAL_AUTH_BYPASS_EMAIL", email)


def reset_portal_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PORTAL_GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("PORTAL_GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("PORTAL_GOOGLE_REDIRECT_URI", raising=False)
    monkeypatch.delenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", raising=False)
    monkeypatch.delenv("WEBSITE_INSTANCE_ID", raising=False)
    monkeypatch.delenv("PORTAL_AUTH_BYPASS_ENABLED", raising=False)
    monkeypatch.delenv("PORTAL_AUTH_BYPASS_DISPLAY_NAME", raising=False)
    monkeypatch.delenv("PORTAL_AUTH_BYPASS_EMAIL", raising=False)


def configure_portal_google_group_auth_env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    allowed_group_keys: str = "group-a@example.com,group-b@example.com",
) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", allowed_group_keys)


def parse_set_cookie_value(set_cookie_header: str, cookie_name: str) -> str:
    cookie = SimpleCookie()
    cookie.load(set_cookie_header)
    return cookie[cookie_name].value


def build_cookie_header(**cookie_values: str) -> str:
    return "; ".join(f"{cookie_name}={cookie_value}" for cookie_name, cookie_value in cookie_values.items())


def test_portal_login_page_shows_google_setup_message_when_not_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)

    response = portal_login_page(build_request("http://localhost:7075/portal"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "<html lang=\"zh-TW\">" in body
    assert "<title>文件管理平台 - iPlayground</title>" in body
    assert '<h1 id="portal-title">文件管理平台</h1>' in body
    assert '<p class="panel-kicker">管理者登入</p>' in body
    assert "Google 登入尚未設定完成" in body
    assert "PORTAL_GOOGLE_CLIENT_ID" in body
    assert "PORTAL_GOOGLE_CLIENT_SECRET" in body
    assert "Google 登入尚未設定" in body
    assert "http://localhost:7075/portal/auth/google/callback" not in body
    assert 'href="/"' in body
    assert "返回首頁" in body
    assert 'class="portal-sso-button portal-action-link"' not in body
    assert 'class="portal-identity-card"' not in body
    assert 'id="form-feedback"' in body
    assert 'id="portal-login-form"' not in body
    assert 'type="password"' not in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/portal.css"' in body
    assert 'src="/assets/page-alert.js"' in body
    assert 'src="/assets/portal-login.js"' in body
    assert 'src="/assets/logo_b_alpha.png"' in body


def test_portal_login_page_uses_portal_google_auth_entry_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    response = portal_login_page(build_request("http://localhost:7075/portal"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' in body
    assert 'class="secondary-button portal-action-link"' in body
    assert 'href="/"' in body
    assert "返回首頁" in body
    assert "請使用 Google Workspace 管理者帳號登入以繼續操作。" not in body
    assert "目前僅開放 iplayground.io 網域帳號登入。" not in body
    assert "Google 群組授權尚未設定" not in body


def test_portal_login_page_shows_group_auth_setup_message_when_group_authorization_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")

    response = portal_login_page(build_request("http://localhost:7075/portal"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "Google 群組授權尚未設定完成" in body
    assert "PORTAL_GOOGLE_ALLOWED_GROUP_KEYS" in body
    assert "Google 群組授權尚未設定" in body
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' not in body


def test_portal_login_page_shows_google_login_cancelled_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
            headers={"Cookie": build_cookie_header(portal_flash="google-login-cancelled")},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert 'class="page-alert"' in body
    assert "data-page-alert" in body
    assert 'data-page-alert-tone="error"' in body
    assert "data-page-alert-dismiss-delay" not in body
    assert 'class="page-alert-frame"' in body
    assert 'class="page-alert-content"' in body
    assert "Google 登入未完成" in body
    assert "已取消 Google 登入。若仍需進入管理平台，請再試一次。" in body
    assert 'data-page-alert-dismiss' in body
    assert 'id="form-feedback"' not in body
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' in body
    assert "返回首頁" in body
    assert 'class="portal-toast"' not in body
    assert "portal_error" not in body
    assert response.headers["Set-Cookie"].startswith("portal_flash=;")


def test_portal_login_alert_dismiss_delay_uses_login_page_setting() -> None:
    assert (
        resolve_portal_login_alert_dismiss_delay_ms(
            PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR
        )
        is None
    )
    assert resolve_portal_login_alert_dismiss_delay_ms("unknown-login-error") is None


def test_portal_login_page_shows_google_login_not_authorized_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
            headers={"Cookie": build_cookie_header(portal_flash="google-login-not-authorized")},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "沒有文件管理平台權限" in body
    assert "此帳號不在允許群組中，請聯絡管理員。" in body
    assert "資料授權未完成" not in body
    assert "請完成資料授權後再登入。" not in body
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' in body


def test_portal_login_page_shows_google_login_data_authorization_required_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
            headers={"Cookie": build_cookie_header(portal_flash="google-login-data-authorization-required")},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "資料授權未完成" in body
    assert "請完成資料授權後再登入。" in body
    assert "沒有文件管理平台權限" not in body
    assert "此帳號不在允許群組中" not in body
    assert "email" not in body
    assert "群組資訊" not in body
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' in body


def test_portal_login_page_shows_google_login_authorization_check_failed_alert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
            headers={"Cookie": build_cookie_header(portal_flash="google-login-authorization-check-failed")},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "群組驗證未完成" in body
    assert "群組驗證未完成，請稍後再試。" in body
    assert "資料授權未完成" not in body
    assert "此帳號不在允許群組中" not in body
    assert '/portal/auth/google/login?post_login_redirect_uri=/portal' in body


def test_portal_login_page_redirects_to_dashboard_when_user_is_authenticated_with_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/dashboard"
    assert response.headers["Cache-Control"] == "no-store"


def test_portal_login_page_redirects_to_dashboard_when_bypass_email_is_external_domain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(
        monkeypatch,
        display_name="網域管理者",
        email="viewer@example.com",
    )

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/dashboard"
    assert response.headers["Cache-Control"] == "no-store"


def test_portal_login_page_redirects_to_dashboard_when_authenticated_user_email_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(
        monkeypatch,
        display_name="陳小華",
        email=None,
    )

    response = portal_login_page(
        build_request(
            "http://localhost:7075/portal",
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/dashboard"
    assert response.headers["Cache-Control"] == "no-store"


def test_portal_dashboard_page_redirects_to_portal_when_not_authenticated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)

    response = portal_dashboard_page(build_request("http://localhost:7075/portal/dashboard"))

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"


def test_portal_dashboard_page_returns_html_when_authenticated_email_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(
        monkeypatch,
        display_name="陳小華",
        email=None,
    )

    response = portal_dashboard_page(
        build_request(
            "http://localhost:7075/portal/dashboard",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "陳小華" in body
    assert "目前登入管理者" in body


def test_portal_dashboard_page_returns_html_with_authenticated_user_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch, display_name="系統管理者")

    response = portal_dashboard_page(
        build_request(
            "http://localhost:7075/portal/dashboard",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "<html lang=\"zh-TW\">" in body
    assert "<title>文件管理平台 - iPlayground</title>" in body
    assert 'id="portal-dashboard"' in body
    assert 'class="portal-dashboard-shell"' in body
    assert 'data-portal-entry-path="/portal"' in body
    assert 'data-logout-url="/portal/auth/logout?post_logout_redirect_uri=/portal"' in body
    assert 'data-welcome-page-path="/portal/dashboard/welcome"' in body
    assert 'id="portal-dashboard-title"' in body
    assert 'data-view-target="welcome"' in body
    assert body.index('data-view-target="events"') < body.index(
        'data-view-target="completion-certs"'
    )
    assert body.index('data-view-target="events"') < body.index(
        'data-view-target="tax-receipts"'
    )
    assert 'data-view-target="completion-certs"' in body
    assert 'data-view-target="tax-receipts"' in body
    assert 'data-view-target="events"' in body
    assert 'data-view-path="/portal/dashboard/welcome"' in body
    assert 'data-view-path="/portal/dashboard/completion-certs"' in body
    assert 'data-view-path="/portal/dashboard/tax-receipts"' in body
    assert 'data-view-path="/portal/dashboard/events"' in body
    assert "檢視清單" not in body
    assert "上傳清單" not in body
    assert "活動管理" in body
    assert "活動與文件設定" in body
    assert "清單與資料上傳" in body
    assert "內容規劃中" in body
    assert "管理活動與可申請文件" not in body
    assert "清單檢視與上傳完訓證明資料" not in body
    assert "清單檢視與上傳 407 收據聯" not in body
    assert 'id="portal-event-create-dialog"' in body
    assert 'id="portal-completion-upload-dialog"' in body
    assert 'class="event-dialog-backdrop portal-event-dialog-backdrop"' in body
    assert 'id="portal-event-name-input"' in body
    assert body.count('autocomplete="off"') == 1
    assert body.count('data-1p-ignore="true"') == 1
    assert body.count('data-op-ignore="true"') == 1
    assert body.count('data-lpignore="true"') == 1
    assert body.count('data-bwignore="true"') == 1
    assert body.count('data-protonpass-ignore="true"') == 1
    assert body.count('data-form-type="other"') == 1
    assert 'id="portal-completion-upload-file"' in body
    assert 'id="portal-completion-upload-file-name"' in body
    assert 'id="portal-completion-upload-submit"' in body
    assert 'id="portal-completion-upload-event"' in body
    assert 'id="portal-completion-upload-event-select"' in body
    assert 'id="portal-completion-upload-event-trigger"' in body
    assert 'id="portal-completion-upload-event-options"' in body
    assert 'id="portal-completion-upload-event-value"' in body
    assert 'aria-labelledby="portal-completion-upload-event-label portal-completion-upload-event-value"' in body
    assert 'class="document-upload-input"' in body
    assert 'class="document-upload-copy"' in body
    assert 'class="document-upload-file-name"' in body
    assert 'accept=".csv,text/csv"' in body
    assert "僅支援 CSV 檔案" in body
    assert "尚未選擇 CSV 檔案" in body
    assert ".xlsx" not in body
    assert ".xls" not in body
    assert "Excel" not in body
    assert 'id="portal-completion-upload-cancel"' in body
    assert 'id="portal-event-create-close"' not in body
    assert "關閉建立活動畫面" not in body
    assert 'class="event-status-switch-option"' in body
    assert 'class="event-status-switch-input"' in body
    assert 'class="event-status-switch-track"' in body
    assert 'id="portal-event-status-checkbox"' in body
    assert 'value="open"' in body
    assert "草稿" not in body
    assert "下架" in body
    assert "開放" in body
    assert "完訓證明" in body
    assert "營業稅繳稅證明" in body
    assert "開放協會 407 收據聯影本供下載" in body
    assert "適用營業稅繳稅資料" not in body
    assert "參與證明" not in body
    assert "志工服務證明" not in body
    assert 'src="/assets/logo_sq_b.png"' in body
    assert 'class="panel admin-workspace"' in body
    assert 'class="sidebar-account-panel"' in body
    assert 'id="admin-account-display">系統管理者<' in body
    assert 'id="portal-logout"' in body
    assert "登出" in body
    assert 'class="admin-content-frame"' in body
    assert 'src="/portal/dashboard/welcome"' in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/portal.css"' in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard.js"' in body
    assert 'data-portal-account-storage-key="portalSignedInAccount"' not in body
    assert 'id="portal-login-form"' not in body


def test_portal_google_auth_callback_sets_session_cookie_and_allows_dashboard_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    monkeypatch.setattr(
        "src.shared.portal_auth._load_google_oidc_configuration",
        lambda: {
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._exchange_portal_google_authorization_code",
        lambda **_: {
            "access_token": "google-access-token",
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._fetch_portal_google_userinfo",
        lambda _: {
            "sub": "google-user-id",
            "name": "本機 Google 管理者",
            "email": "admin@iplayground.io",
            "email_verified": True,
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth.is_portal_google_user_in_allowed_group",
        lambda email, access_token: email == "admin@iplayground.io" and access_token == "google-access-token",
    )

    login_response = portal_google_login_page(
        build_request(
            "http://localhost:7075/portal/auth/google/login",
            params={"post_login_redirect_uri": "/portal"},
        )
    )
    state_cookie_header = login_response.headers["Set-Cookie"]
    state_token = parse_set_cookie_value(state_cookie_header, "portal_google_oauth_state")

    callback_response = portal_google_callback_page(
        build_request(
            "http://localhost:7075/portal/auth/google/callback",
            headers={"Cookie": f"portal_google_oauth_state={state_token}"},
            params={
                "code": "google-auth-code",
                "state": state_token,
            },
        )
    )

    assert callback_response.status_code == 302
    assert callback_response.headers["Location"] == "/portal"
    assert "cloud-identity.groups.readonly" in login_response.headers["Location"]
    session_cookie_header = callback_response.headers["Set-Cookie"]
    session_token = parse_set_cookie_value(session_cookie_header, "portal_google_session")

    dashboard_response = portal_dashboard_page(
        build_request(
            "http://localhost:7075/portal/dashboard",
            headers={"Cookie": f"portal_google_session={session_token}"},
        )
    )
    dashboard_body = dashboard_response.get_body().decode("utf-8")

    assert dashboard_response.status_code == 200
    assert 'id="admin-account-display">本機 Google 管理者<' in dashboard_body
    assert 'data-logout-url="/portal/auth/logout?post_logout_redirect_uri=/portal"' in dashboard_body


def test_portal_google_auth_callback_redirects_to_portal_when_data_authorization_is_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")

    response = portal_google_callback_page(
        build_request(
            "http://localhost:7075/portal/auth/google/callback",
            params={"error": "access_denied"},
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"
    assert response.headers["Cache-Control"] == "no-store"
    assert parse_set_cookie_value(response.headers["Set-Cookie"], "portal_flash") == "google-login-data-authorization-required"


def test_portal_google_auth_callback_redirects_to_portal_when_verified_email_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    monkeypatch.setattr(
        "src.shared.portal_auth._exchange_portal_google_authorization_code",
        lambda **_: {
            "access_token": "google-access-token",
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._fetch_portal_google_userinfo",
        lambda _: {
            "sub": "google-user-id",
            "name": "缺少 email 帳號",
            "email": "",
            "email_verified": False,
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._verify_portal_google_token",
        lambda token, secret: {"post_login_redirect_uri": "/portal"} if token == "demo-state" else None,
    )

    response = portal_google_callback_page(
        build_request(
            "http://localhost:7075/portal/auth/google/callback",
            headers={"Cookie": "portal_google_oauth_state=demo-state"},
            params={
                "code": "google-auth-code",
                "state": "demo-state",
            },
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"
    assert parse_set_cookie_value(response.headers["Set-Cookie"], "portal_flash") == "google-login-data-authorization-required"


def test_portal_google_auth_callback_redirects_to_portal_when_google_account_is_not_in_allowed_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    monkeypatch.setattr(
        "src.shared.portal_auth._exchange_portal_google_authorization_code",
        lambda **_: {
            "access_token": "google-access-token",
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._fetch_portal_google_userinfo",
        lambda _: {
            "sub": "google-user-id",
            "name": "未授權帳號",
            "email": "member@iplayground.io",
            "email_verified": True,
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth.is_portal_google_user_in_allowed_group",
        lambda _email, _access_token: False,
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._verify_portal_google_token",
        lambda token, secret: {"post_login_redirect_uri": "/portal"} if token == "demo-state" else None,
    )

    response = portal_google_callback_page(
        build_request(
            "http://localhost:7075/portal/auth/google/callback",
            headers={"Cookie": "portal_google_oauth_state=demo-state"},
            params={
                "code": "google-auth-code",
                "state": "demo-state",
            },
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"
    assert parse_set_cookie_value(response.headers["Set-Cookie"], "portal_flash") == "google-login-not-authorized"


def test_portal_google_auth_callback_redirects_to_portal_when_group_check_does_not_authorize_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")
    configure_portal_google_group_auth_env(monkeypatch)

    monkeypatch.setattr(
        "src.shared.portal_auth._exchange_portal_google_authorization_code",
        lambda **_: {
            "access_token": "google-access-token",
        },
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._fetch_portal_google_userinfo",
        lambda _: {
            "sub": "google-user-id",
            "name": "檢查失敗帳號",
            "email": "member@iplayground.io",
            "email_verified": True,
        },
    )

    def raise_group_authorization_error(_email: str, _access_token: str) -> bool:
        raise PortalGoogleGroupAuthorizationError("找不到指定的 Google 群組，或目前登入的 Google 帳號無法查看該群組。")

    monkeypatch.setattr(
        "src.shared.portal_auth.is_portal_google_user_in_allowed_group",
        raise_group_authorization_error,
    )
    monkeypatch.setattr(
        "src.shared.portal_auth._verify_portal_google_token",
        lambda token, secret: {"post_login_redirect_uri": "/portal"} if token == "demo-state" else None,
    )

    response = portal_google_callback_page(
        build_request(
            "http://localhost:7075/portal/auth/google/callback",
            headers={"Cookie": "portal_google_oauth_state=demo-state"},
            params={
                "code": "google-auth-code",
                "state": "demo-state",
            },
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"
    assert (
        parse_set_cookie_value(response.headers["Set-Cookie"], "portal_flash")
        == "google-login-authorization-check-failed"
    )


def test_portal_google_logout_clears_session_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_ID", "portal-client-id")
    monkeypatch.setenv("PORTAL_GOOGLE_CLIENT_SECRET", "portal-client-secret")

    response = portal_google_logout_page(
        build_request(
            "http://localhost:7075/portal/auth/logout",
            params={"post_logout_redirect_uri": "/portal"},
        )
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "/portal"
    assert "portal_google_session=;" in response.headers["Set-Cookie"]


def test_portal_dashboard_welcome_page_returns_html_with_authenticated_user_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch, display_name="系統管理者")

    response = portal_dashboard_welcome_page(
        build_request(
            "http://localhost:7075/portal/dashboard/welcome",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "<title>文件管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert 'class="embedded-page-shell"' in body
    assert 'id="welcome-account-display">系統管理者<' in body
    assert 'id="portal-logout"' not in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "歡迎回來" in body
    assert "你可以在這裡上傳文件申請清單、追蹤批次處理結果" in body
    assert "系統可下載數" in body
    assert "下載人數" in body
    assert "驗證次數" in body
    assert "待處理案件數量" in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard-welcome.js"' in body


def test_portal_dashboard_completion_certs_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_completion_certs_page(
        build_request(
            "http://localhost:7075/portal/dashboard/completion-certs",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>完訓證明 - 文件管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" in body
    assert "完訓證明" in body
    assert "完訓證明資料清單" in body
    assert "套用至目前活動全部資料" in body
    assert "全選目前清單" not in body
    assert "已選取 0 筆" not in body
    assert "設為已簽到" in body
    assert "設為未簽到" in body
    assert "設為已簽到可下載" not in body
    assert "設為未簽到不可下載" not in body
    assert 'id="completion-bulk-toolbar"' in body
    assert 'id="completion-select-all"' not in body
    assert 'id="completion-selection-count"' not in body
    assert 'id="completion-bulk-downloadable"' in body
    assert 'id="completion-bulk-blocked"' in body
    assert 'class="document-bulk-toolbar"' in body
    assert 'class="document-bulk-scope"' in body
    assert 'class="document-selection-option"' not in body
    assert 'class="document-bulk-actions"' in body
    assert 'class="secondary-button document-bulk-action"' in body
    assert "簽到狀態" in body
    assert "未簽到" in body
    assert "已簽到" in body
    assert "不可下載" not in body
    assert "可下載" not in body
    assert "報名序號" in body
    assert "票種" in body
    assert "操作" in body
    assert "下載" in body
    assert 'id="completion-cert-row-template"' in body
    assert 'id="completion-cert-table-body"' in body
    assert 'id="completion-cert-empty-row"' in body
    assert 'class="secondary-button document-download-button"' in body
    assert 'class="document-row-checkbox"' not in body
    assert 'class="event-status-switch-option document-row-status-switch"' in body
    assert 'class="event-status-switch-input document-download-switch-input"' in body
    assert 'data-action="toggle-downloadable"' in body
    assert 'data-field="downloadStatus"' in body
    assert 'data-field="downloadState"' not in body
    assert 'aria-label="切換簽到狀態"' in body
    assert 'data-field="ticketType"' in body
    assert 'colspan="6"' in body
    assert "上傳完訓證明資料" in body
    assert 'class="document-filter-form"' in body
    assert 'aria-label="完訓證明資料篩選"' in body
    assert '<th scope="col">活動</th>' not in body
    assert 'data-field="eventName"' not in body
    assert 'class="custom-select"' in body
    assert 'class="custom-select-trigger"' in body
    assert 'class="custom-select-menu"' in body
    assert 'class="custom-select-option is-selected"' in body
    assert 'role="listbox"' in body
    assert 'role="option"' in body
    assert 'id="completion-event-filter"' in body
    assert 'type="hidden"' in body
    assert 'name="eventName"' in body
    assert 'aria-required="true"' in body
    assert "<select" not in body
    assert "iPlayground 2026" in body
    assert "必填" not in body
    assert "套用篩選" not in body
    assert "completion-upload-file" in body
    assert 'id="completion-upload-file-name"' in body
    assert 'id="completion-upload-submit"' in body
    assert 'id="completion-upload-event"' in body
    assert 'id="completion-upload-event-select"' in body
    assert 'id="completion-upload-event-trigger"' in body
    assert 'id="completion-upload-event-options"' in body
    assert 'id="completion-upload-event-value"' in body
    assert 'aria-labelledby="completion-upload-event-label completion-upload-event-value"' in body
    assert 'class="document-upload-input"' in body
    assert 'class="document-upload-copy"' in body
    assert 'class="document-upload-file-name"' in body
    assert 'accept=".csv,text/csv"' in body
    assert "僅支援 CSV 檔案" in body
    assert "尚未選擇 CSV 檔案" in body
    assert ".xlsx" not in body
    assert ".xls" not in body
    assert "Excel" not in body
    assert 'id="completion-upload-open"' in body
    assert 'id="completion-upload-dialog"' in body
    assert 'aria-modal="true"' in body
    assert 'id="completion-upload-cancel"' in body
    assert 'src="/assets/portal-dashboard-completion-certs.js"' in body
    assert "document-workspace-grid" not in body
    assert "上傳資料" not in body
    assert '<p class="panel-kicker">完訓證明</p>' not in body
    assert "清單檢視" not in body
    assert "尚未串接完訓證明資料來源" in body
    assert "獨立工作頁" not in body


def test_portal_dashboard_tax_receipts_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_tax_receipts_page(
        build_request(
            "http://localhost:7075/portal/dashboard/tax-receipts",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>營業稅繳稅證明 - 文件管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" not in body
    assert "清單檢視" not in body
    assert "營業稅繳稅證明清單" not in body
    assert "上傳 407 收據聯" not in body
    assert "tax-upload-file" not in body
    assert "尚未串接 407 收據聯資料來源" not in body
    assert "獨立工作頁" not in body


def test_portal_dashboard_events_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_events_page(
        build_request(
            "http://localhost:7075/portal/dashboard/events",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>活動管理 - 文件管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "event-management-card" in body
    assert "event-management-panel" not in body
    assert "event-panel-heading" not in body
    assert 'id="event-list-title"' not in body
    assert "活動管理" in body
    assert "活動清單" in body
    assert 'class="event-list-col-name"' in body
    assert 'class="event-list-col-code"' not in body
    assert 'class="event-list-col-documents"' in body
    assert 'class="event-list-col-status"' in body
    assert 'class="event-list-row"' in body
    assert 'role="button"' in body
    assert 'aria-label="編輯活動 iPlayground 2026"' in body
    assert 'data-event-form-open="edit"' in body
    assert 'data-event-name="iPlayground 2026"' in body
    assert 'data-event-status="open"' in body
    assert 'data-event-document-types="completionCert"' in body
    assert "活動代碼" not in body
    assert "ipg-2026" not in body
    assert 'id="event-code-input"' not in body
    assert "申請期間" not in body
    assert "申請起始日" not in body
    assert "申請截止日" not in body
    assert 'id="event-create-open"' in body
    assert "建立活動" in body
    assert 'id="event-create-dialog"' in body
    assert body.count('autocomplete="off"') == 1
    assert body.count('data-1p-ignore="true"') == 1
    assert body.count('data-op-ignore="true"') == 1
    assert body.count('data-lpignore="true"') == 1
    assert body.count('data-bwignore="true"') == 1
    assert body.count('data-protonpass-ignore="true"') == 1
    assert body.count('data-form-type="other"') == 1
    assert 'aria-modal="true"' in body
    assert 'class="secondary-button event-cancel-button"' in body
    assert 'id="event-create-close"' not in body
    assert "關閉建立活動畫面" not in body
    assert "活動狀態" in body
    assert 'class="event-status-switch-option"' in body
    assert 'class="event-status-switch-input"' in body
    assert 'class="event-status-switch-track"' in body
    assert 'id="event-status-checkbox"' in body
    assert 'value="open"' in body
    assert 'role="listbox"' not in body
    assert 'role="option"' not in body
    assert 'aria-expanded="false"' not in body
    assert "草稿" not in body
    assert "下架" in body
    assert "開放" in body
    assert "可申請文件類型" in body
    assert "完訓證明" in body
    assert "營業稅繳稅證明" in body
    assert "開放協會 407 收據聯影本供下載" in body
    assert 'value="taxReceipt"' in body
    assert "適用營業稅繳稅資料" not in body
    assert "參與證明" not in body
    assert "志工服務證明" not in body
    assert "已開通" not in body
    assert 'src="/assets/portal-dashboard-events.js"' in body


def test_portal_css_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal.css",
            route_params={"asset_name": "portal.css"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert ".portal-card" in body
    assert ".portal-auth-actions" in body
    assert ".portal-auth-lead" in body
    assert ".portal-identity-card" in body
    assert ".portal-action-link" in body
    assert ".portal-sso-button" in body
    assert ".portal-sso-button-icon" in body
    assert ".portal-sso-button-copy" in body
    assert ".portal-sso-button-label" in body
    assert ".page-alert" not in body
    assert ".panel.admin-workspace" in body
    assert ".portal-dashboard-shell .page-shell" in body
    assert ".portal-dashboard-shell .panel.admin-workspace" in body
    assert ".admin-sidebar" in body
    assert ".admin-content-frame" in body
    assert ".portal-embedded-body" in body
    assert ".embedded-page-shell" in body
    assert ".admin-header" in body
    assert ".admin-header-title" in body
    assert ".admin-account-panel" in body
    assert ".sidebar-account-panel" in body
    assert ".sidebar-account-panel .secondary-button" in body
    assert ".welcome-brand-row" in body
    assert ".admin-nav-item.is-active" in body
    assert ".metric-grid" in body
    assert ".event-management-card" in body
    assert ".custom-select-trigger" in body
    assert ".custom-select-menu" in body
    assert ".custom-select-option" in body
    assert ".document-workspace-card" in body
    assert ".document-filter-form" in body
    assert ".document-bulk-toolbar" in body
    assert ".document-bulk-scope" in body
    assert ".document-selection-option" not in body
    assert ".document-selection-count" not in body
    assert ".document-bulk-actions" in body
    assert ".document-bulk-action:disabled" in body
    assert ".document-list-select-col" not in body
    assert ".document-selection-cell" not in body
    assert ".document-row-checkbox" not in body
    assert ".document-row-status-switch" in body
    assert ".document-row-status-copy" in body
    assert ".document-download-switch-input" in body
    assert ".required-field-mark" not in body
    assert ".document-filter-submit" not in body
    assert ".document-list-table" in body
    assert ".document-download-button" in body
    assert ".document-download-button:disabled" in body
    assert ".document-upload-form" in body
    assert ".document-upload-dropzone" in body
    assert ".document-upload-input" in body
    assert ".document-upload-copy" in body
    assert ".document-upload-file-name" in body
    assert ".document-upload-form input[type=\"file\"]" not in body
    assert ".event-management-header" in body
    assert ".event-management-panel" not in body
    assert ".event-list-toolbar" not in body
    assert ".event-list-table" in body
    assert ".event-list-col-documents" in body
    assert ".event-list-col-code" not in body
    assert ".event-list-row" in body
    assert "white-space: nowrap;" in body
    assert "text-align: center;" in body
    assert ".portal-dashboard-shell.has-event-dialog" in body
    assert ".portal-embedded-body.has-event-dialog" in body
    assert ".event-dialog-backdrop" in body
    assert "background: rgba(13, 21, 39, 0.68);" in body
    assert "background: #fff;" in body
    assert ".event-status-select" not in body
    assert ".event-status-checkbox-option" not in body
    assert ".event-status-inline-option" not in body
    assert ".event-status-switch-option" in body
    assert ".event-status-switch-input:checked + .event-status-switch-track" in body
    assert ".event-status-switch-thumb" in body
    assert "transform: translateX(18px);" in body
    assert "select-caret" in body
    assert ".event-status-badge.is-draft" not in body
    assert ".event-status-badge.is-unlisted" in body
    assert ".event-status-badge.is-open" in body
    assert ".document-type-option" in body
    assert "background-image: none;" in body
    assert ".event-cancel-button" in body
    assert "border-radius: 14px;" not in body
    assert "accent-color: var(--theme-accent-deep);" in body
    assert "appearance: auto;" in body
    assert "color-scheme: light;" in body
    assert "accent-color: #ea6e1e;" in body
    assert "border: 2px solid #f2865e;" not in body
    assert ".sidebar-brand" in body
    assert "object-fit: cover;" in body
    assert "color: #fff;" in body
    assert "margin: 0 auto;" in body
    assert "var(--theme-body-bg)" in body
    assert "var(--theme-card-overlay)" in body
    assert "@media (max-width: 960px)" in body


def test_portal_login_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-login.js",
            route_params={"asset_name": "portal-login.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.querySelectorAll(".portal-action-link")' in body
    assert 'link.dataset.loadingLabel?.trim()' in body
    assert 'link.setAttribute("aria-disabled", "true")' in body
    assert 'link.classList.add("is-busy")' in body
    assert "pageAlert" not in body
    assert "validateLoginForm" not in body
    assert "sessionStorage" not in body


def test_page_alert_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/page-alert.js",
            route_params={"asset_name": "page-alert.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.querySelectorAll("[data-page-alert]")' in body
    assert 'pageAlert.querySelector("[data-page-alert-dismiss]")' in body
    assert 'pageAlert.classList.add("is-closing")' in body
    assert 'pageAlert.addEventListener("animationend"' in body
    assert 'event.animationName !== "page-alert-dissolve"' in body
    assert 'pageAlert.classList.add("is-hidden")' in body
    assert "pageAlert.dataset.pageAlertDismissDelay" in body


def test_portal_dashboard_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard.js",
            route_params={"asset_name": "portal-dashboard.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'const portalEntryPath = portalPage.dataset.portalEntryPath ?? "/portal";' in body
    assert 'const logoutUrl =' in body
    assert "syncPageTitleFromFrame" in body
    assert "document.title = nextTitle" in body
    assert "activateView" in body
    assert "syncViewFromFrame" in body
    assert "openDashboardEventDialog" in body
    assert "openDashboardCompletionUploadDialog" in body
    assert "portal-completion-upload-file-name" in body
    assert "portal-completion-upload-submit" in body
    assert "portal-completion-upload-event" in body
    assert "portal-completion-upload-event-trigger" in body
    assert "updateDashboardCompletionUploadFileName" in body
    assert "isDashboardCompletionCsvFile" in body
    assert "getCompletionEventNameFromFrame" in body
    assert "applyDashboardCompletionUploadEventValue" in body
    assert "getDashboardCompletionUploadEventName" in body
    assert "openDashboardCompletionUploadEventSelect" in body
    assert "closeDashboardCompletionUploadEventSelect" in body
    assert "sendDashboardCompletionUploadFileToFrame" in body
    assert "completionUploadImportMessageType" in body
    assert "ipg:completion-upload:import" in body
    assert "eventName: getDashboardCompletionUploadEventName()" in body
    assert "selectedFile.text()" in body
    assert "contentFrame.contentWindow?.postMessage" in body
    assert '.endsWith(".csv")' in body
    assert "setDashboardEventDialogMode" in body
    assert "applyDashboardEventStatusValue" in body
    assert "dashboardEventStatusCheckbox" in body
    assert "openDashboardEventStatusSelect" not in body
    assert "closeDashboardEventStatusSelect" not in body
    assert "collectDashboardEventDialogState" in body
    assert "confirmDashboardEventDialogClose" in body
    assert "資料尚未存檔，確定要取消嗎？" in body
    assert "closeDashboardEventCreateDialog" in body
    assert "ipg:event-form:open" in body
    assert "ipg:completion-upload:open" in body
    assert "儲存變更" in body
    assert 'pageShell?.setAttribute("inert", "")' in body
    assert 'pageShell?.setAttribute("aria-hidden", "true")' in body
    assert 'contentFrame.src = targetButton.dataset.viewPath ?? welcomePagePath' in body
    assert "contentFrame.addEventListener" in body
    assert "button.dataset.viewTarget" in body
    assert "button.dataset.viewPath" in body
    assert 'window.location.assign(logoutUrl)' in body
    assert 'window.location.assign(portalEntryPath)' in body
    assert "sessionStorage" not in body


def test_portal_dashboard_completion_certs_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard-completion-certs.js",
            route_params={"asset_name": "portal-dashboard-completion-certs.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.getElementById("completion-upload-open")' in body
    assert 'document.getElementById("completion-upload-file-name")' in body
    assert 'document.getElementById("completion-upload-submit")' in body
    assert 'document.getElementById("completion-upload-event")' in body
    assert '"completion-upload-event-trigger"' in body
    assert 'document.getElementById("completion-select-all")' not in body
    assert 'document.getElementById("completion-bulk-downloadable")' in body
    assert 'document.getElementById("completion-bulk-blocked")' in body
    assert "updateCompletionUploadFileName" in body
    assert "isCompletionCsvFile" in body
    assert "completionUploadImportMessageType" in body
    assert "ipg:completion-upload:import" in body
    assert "getCompletionUploadEventName" in body
    assert "applyCompletionUploadEventValue" in body
    assert "openCompletionUploadEventSelect" in body
    assert "closeCompletionUploadEventSelect" in body
    assert "getVisibleCompletionCertRows" in body
    assert "message.eventName" in body
    assert "parseCompletionCsv" in body
    assert "buildCompletionCertRows" in body
    assert "renderCompletionCertRows" in body
    assert "importCompletionCsvText" in body
    assert "setCompletionRowDownloadState" in body
    assert "setCompletionSelectionForAllRows" not in body
    assert "applyDownloadableStateToSelection" not in body
    assert "applyDownloadableStateToCurrentActivity" in body
    assert "未簽到" in body
    assert "已簽到" in body
    assert "不可下載" not in body
    assert "可下載" not in body
    assert '.endsWith(".csv")' in body
    assert 'document.querySelector(".document-filter-form")' in body
    assert 'document.getElementById("completion-event-filter")' in body
    assert '"completion-event-filter-trigger"' in body
    assert "completionEventFilterOptions.forEach" in body
    assert "event.preventDefault()" in body
    assert "applyCompletionFilters" in body
    assert "applyCompletionEventFilterValue" in body
    assert "openCompletionEventFilterSelect" in body
    assert "closeCompletionEventFilterSelect" in body
    assert "openCompletionUploadDialog" in body
    assert "requestParentCompletionUploadDialog" in body
    assert "window.parent.postMessage" in body
    assert "window.parent !== window" in body
    assert "ipg:completion-upload:open" in body
    assert "completionUploadDialog.hidden = false" in body
    assert "confirmCompletionUploadDialogClose" in body
    assert "資料尚未存檔，確定要取消嗎？" in body
    assert 'event.key === "Escape"' in body
    assert "sessionStorage" not in body


def test_portal_dashboard_events_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard-events.js",
            route_params={"asset_name": "portal-dashboard-events.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.getElementById("event-create-open")' in body
    assert "openEventCreateDialog" in body
    assert "openEventEditDialog" in body
    assert "setEventDialogMode" in body
    assert "applyEventStatusValue" in body
    assert "eventStatusCheckbox" in body
    assert "openEventStatusSelect" not in body
    assert "closeEventStatusSelect" not in body
    assert "collectEventDialogState" in body
    assert "confirmEventDialogClose" in body
    assert "資料尚未存檔，確定要取消嗎？" in body
    assert "closeEventCreateDialog" in body
    assert "requestParentEventFormDialog" in body
    assert "window.parent.postMessage" in body
    assert "window.parent !== window" in body
    assert "data-event-form-open" in body
    assert "儲存變更" in body
    assert 'event.key !== "Enter" && event.key !== " "' in body
    assert "eventCreateDialog.hidden = false" in body
    assert "eventCode" not in body
    assert 'event.key === "Escape"' in body


def test_favicon_asset_returns_expected_content_type_for_portal_pages() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/favicon.png",
            route_params={"asset_name": "favicon.png"},
        )
    )
    body = response.get_body()

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert body.startswith(b"\x89PNG")


def test_google_g_icon_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/google-g-icon.svg",
            route_params={"asset_name": "google-g-icon.svg"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert 'viewBox="0 0 20 20"' in body
    assert 'fill="#4285F4"' in body


def test_portal_dashboard_welcome_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard-welcome.js",
            route_params={"asset_name": "portal-dashboard-welcome.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "ensureWelcomeAccountDisplay" in body
    assert 'welcomeAccountDisplay.textContent = "管理者"' in body
    assert "sessionStorage" not in body
    assert "logoutButton.addEventListener" not in body


def test_portal_sidebar_logo_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/logo_sq_b.png",
            route_params={"asset_name": "logo_sq_b.png"},
        )
    )

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert len(response.get_body()) > 0


def test_portal_login_page_shows_setup_message_on_azure_when_portal_google_auth_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    monkeypatch.setenv("WEBSITE_INSTANCE_ID", "azure-instance")

    response = portal_login_page(build_request("https://cert.iplayground.io/portal"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "Google 登入尚未設定完成" in body
    assert "Google 登入尚未設定" in body
    assert "http://localhost:7075/portal/auth/google/callback" not in body
