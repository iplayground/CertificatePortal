from __future__ import annotations

from http.cookies import SimpleCookie

import azure.functions as func
import pytest

from src.functions.assets import static_asset
from src.functions.portal import (
    PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR,
    portal_dashboard_page,
    portal_dashboard_records_page,
    portal_dashboard_upload_page,
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
    assert "<title>完訓證明管理平台 - iPlayground</title>" in body
    assert '<h1 id="portal-title">完訓證明管理平台</h1>' in body
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
    assert "沒有管理平台權限" in body
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
    assert "沒有管理平台權限" not in body
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
    assert "<title>完訓證明管理平台 - iPlayground</title>" in body
    assert 'id="portal-dashboard"' in body
    assert 'class="portal-dashboard-shell"' in body
    assert 'data-portal-entry-path="/portal"' in body
    assert 'data-logout-url="/portal/auth/logout?post_logout_redirect_uri=/portal"' in body
    assert 'data-welcome-page-path="/portal/dashboard/welcome"' in body
    assert 'id="portal-dashboard-title"' in body
    assert 'data-view-target="welcome"' in body
    assert 'data-view-target="records"' in body
    assert 'data-view-target="upload"' in body
    assert 'data-view-path="/portal/dashboard/welcome"' in body
    assert 'data-view-path="/portal/dashboard/records"' in body
    assert 'data-view-path="/portal/dashboard/upload"' in body
    assert "檢視清單" in body
    assert "上傳清單" in body
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
    assert "<title>完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert 'class="embedded-page-shell"' in body
    assert 'id="welcome-account-display">系統管理者<' in body
    assert 'id="portal-logout"' not in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "歡迎回來" in body
    assert "你可以在這裡上傳完訓名單、追蹤批次處理結果" in body
    assert "系統可下載數" in body
    assert "下載人數" in body
    assert "驗證次數" in body
    assert "待處理案件數量" in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard-welcome.js"' in body


def test_portal_dashboard_records_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_records_page(
        build_request(
            "http://localhost:7075/portal/dashboard/records",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>檢視清單 - 完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" in body
    assert "檢視清單" in body
    assert "獨立工作頁" in body


def test_portal_dashboard_upload_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_upload_page(
        build_request(
            "http://localhost:7075/portal/dashboard/upload",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>上傳清單 - 完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" in body
    assert "上傳清單" in body
    assert "獨立工作頁" in body


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
    assert 'contentFrame.src = targetButton.dataset.viewPath ?? welcomePagePath' in body
    assert "contentFrame.addEventListener" in body
    assert "button.dataset.viewTarget" in body
    assert "button.dataset.viewPath" in body
    assert 'window.location.assign(logoutUrl)' in body
    assert 'window.location.assign(portalEntryPath)' in body
    assert "sessionStorage" not in body


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
