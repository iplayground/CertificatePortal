from __future__ import annotations

import azure.functions as func

from src.functions.assets import static_asset
from src.functions.portal import portal_login_page


def build_request(
    url: str,
    *,
    route_params: dict[str, str] | None = None,
) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url=url,
        headers={},
        params={},
        route_params=route_params or {},
        body=b"",
    )


def test_portal_login_page_returns_html_with_expected_fields() -> None:
    response = portal_login_page(build_request("http://localhost:7075/portal"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "<html lang=\"zh-TW\">" in body
    assert "<title>iPlayground 管理平台登入</title>" in body
    assert '<h1 id="portal-title">管理中心</h1>' in body
    assert '<p class="panel-kicker">管理者登入</p>' in body
    assert '<p class="lead">' not in body
    assert 'class="panel-meta"' not in body
    assert 'class="portal-notes"' not in body
    assert 'data-default-feedback-message=""' in body
    assert 'data-invalid-account-message="請輸入有效的電子郵件地址。"' in body
    assert 'id="portal-login-form"' in body
    assert 'type="email"' in body
    assert 'autocomplete="email"' in body
    assert 'inputmode="email"' in body
    assert 'aria-labelledby="portal-account-label"' in body
    assert 'autocomplete="current-password"' in body
    assert 'aria-labelledby="portal-password-label"' in body
    assert 'id="toggle-password"' in body
    assert 'class="panel portal-card"' in body
    assert 'class="portal-form-shell"' in body
    assert 'type="submit" disabled' in body
    assert 'name="color-scheme"' in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/portal.css"' in body
    assert 'src="/assets/portal.js"' in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "iPlayground Certify" not in body
    assert '<label class="field-label" for="portal-account">' not in body
    assert 'data-empty-account-message="請輸入管理者帳號。"' in body


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
    assert ".portal-form-shell" in body
    assert ".panel-kicker" in body
    assert ".password-toggle" in body
    assert ".submit-button:disabled" in body
    assert ".form-feedback:empty" in body
    assert ".form-feedback.is-error" in body
    assert "color: #fff;" in body
    assert "margin: 0 auto;" in body
    assert "var(--theme-body-bg)" in body
    assert "var(--theme-card-overlay)" in body
    assert "@media (max-width: 960px)" in body


def test_portal_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal.js",
            route_params={"asset_name": "portal.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "validateLoginForm" in body
    assert "updateSubmitState" in body
    assert "setFeedbackState" in body
    assert "syncPasswordToggleLabel" in body
    assert "accountInput.checkValidity()" in body
    assert "submitButton.disabled" in body
    assert 'passwordInput.type = isPasswordHidden ? "text" : "password"' in body
    assert "togglePasswordButton.addEventListener" in body
    assert "accountInput.focus()" in body
