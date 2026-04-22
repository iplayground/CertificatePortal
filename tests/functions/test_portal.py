from __future__ import annotations

import azure.functions as func

from src.functions.assets import static_asset
from src.functions.portal import (
    portal_dashboard_page,
    portal_dashboard_records_page,
    portal_dashboard_upload_page,
    portal_dashboard_welcome_page,
    portal_login_page,
)


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
    assert "<title>完訓證明管理平台 - iPlayground</title>" in body
    assert '<h1 id="portal-title">完訓證明管理平台</h1>' in body
    assert '<p class="panel-kicker">管理者登入</p>' in body
    assert 'id="portal-login-view"' in body
    assert 'id="portal-dashboard"' not in body
    assert 'data-dashboard-page-path="/portal/dashboard"' in body
    assert 'data-portal-account-storage-key="portalSignedInAccount"' in body
    assert 'data-default-feedback-message=""' in body
    assert 'id="portal-login-form"' in body
    assert 'type="text"' in body
    assert 'autocomplete="username"' in body
    assert 'aria-labelledby="portal-account-label"' in body
    assert 'autocomplete="current-password"' in body
    assert 'aria-labelledby="portal-password-label"' in body
    assert 'id="toggle-password"' in body
    assert 'class="panel portal-card"' in body
    assert 'class="panel admin-workspace"' not in body
    assert 'class="portal-form-shell"' in body
    assert 'type="submit" disabled' in body
    assert 'name="color-scheme"' in body
    assert 'href="/assets/favicon.png"' in body
    assert 'sizes="32x32"' in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/portal.css"' in body
    assert 'src="/assets/portal-login.js"' in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "iPlayground Certify" not in body
    assert '<label class="field-label" for="portal-account">' not in body
    assert 'data-empty-account-message="請輸入管理者帳號。"' in body


def test_portal_dashboard_page_returns_html_with_expected_fields() -> None:
    response = portal_dashboard_page(build_request("http://localhost:7075/portal/dashboard"))
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
    assert 'data-home-page-path="/"' in body
    assert 'data-portal-account-storage-key="portalSignedInAccount"' in body
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
    assert 'id="admin-account-display"' in body
    assert 'id="portal-logout"' in body
    assert "返回首頁" in body
    assert 'class="admin-content-frame"' in body
    assert 'src="/portal/dashboard/welcome"' in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/portal.css"' in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard.js"' in body
    assert "完訓證明管理平台" in body
    assert "iPlayground Certify" not in body
    assert 'id="portal-login-form"' not in body
    assert "首頁總覽" not in body


def test_portal_dashboard_welcome_page_returns_html_with_expected_fields() -> None:
    response = portal_dashboard_welcome_page(
        build_request("http://localhost:7075/portal/dashboard/welcome")
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex, nofollow"
    assert "<title>完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert 'data-portal-account-storage-key="portalSignedInAccount"' in body
    assert 'class="embedded-page-shell"' in body
    assert 'id="welcome-account-display"' in body
    assert 'id="portal-logout"' not in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "內部頁面" not in body
    assert "首頁總覽" not in body
    assert "完訓證明管理平台" in body
    assert "歡迎使用完訓證明管理平台" not in body
    assert "管理首頁總覽" not in body
    assert "左側為功能清單，右側為對應頁面內容。" not in body
    assert "目前尚未串接實際登入驗證、清單資料與上傳處理流程" not in body
    assert "歡迎回來" in body
    assert "你可以在這裡上傳完訓名單、追蹤批次處理結果" in body
    assert "系統可下載數" in body
    assert "下載人數" in body
    assert "驗證次數" in body
    assert "待處理案件數量" in body
    assert "今日驗證查詢" not in body
    assert "總批次數" not in body
    assert "可下載證書" not in body
    assert "今日下載次數" not in body
    assert "平台概況" not in body
    assert "最近更新" not in body
    assert "檢視清單" not in body
    assert "上傳清單" not in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard-welcome.js"' in body


def test_portal_dashboard_records_page_returns_html_with_expected_fields() -> None:
    response = portal_dashboard_records_page(
        build_request("http://localhost:7075/portal/dashboard/records")
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>檢視清單 - 完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" in body
    assert "檢視清單" in body
    assert "獨立工作頁" in body
    assert 'href="/assets/favicon.png"' in body


def test_portal_dashboard_upload_page_returns_html_with_expected_fields() -> None:
    response = portal_dashboard_upload_page(
        build_request("http://localhost:7075/portal/dashboard/upload")
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>上傳清單 - 完訓證明管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "embedded-page-card" in body
    assert "上傳清單" in body
    assert "獨立工作頁" in body
    assert 'href="/assets/favicon.png"' in body


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
    assert ".admin-banner" in body
    assert ".admin-nav-item.is-active" in body
    assert ".metric-grid" in body
    assert ".content-section-heading-minimal" in body
    assert ".sidebar-brand" in body
    assert "object-fit: cover;" in body
    assert "color: #fff;" in body
    assert "margin: 0 auto;" in body
    assert "var(--theme-body-bg)" in body
    assert "var(--theme-card-overlay)" in body
    assert "@media (max-width: 960px)" in body
    assert "grid-template-columns: 1fr;" not in body


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
    assert "validateLoginForm" in body
    assert "updateSubmitState" in body
    assert "submitButton.disabled" in body
    assert "persistSignedInAccount" in body
    assert 'window.sessionStorage.setItem(portalAccountStorageKey, accountValue)' in body
    assert "window.location.assign(dashboardPagePath)" in body
    assert 'passwordInput.type = isPasswordHidden ? "text" : "password"' in body
    assert "togglePasswordButton.addEventListener" in body
    assert "accountInput.focus()" in body


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
    assert "syncSignedInAccount" in body
    assert "clearSignedInAccount" in body
    assert 'window.sessionStorage.getItem(portalAccountStorageKey)?.trim() ?? ""' in body
    assert 'window.sessionStorage.removeItem(portalAccountStorageKey)' in body
    assert "logoutButton.addEventListener" in body
    assert "window.location.assign(homePagePath)" in body
    assert "syncPageTitleFromFrame" in body
    assert "document.title = nextTitle" in body
    assert "activateView" in body
    assert "syncViewFromFrame" in body
    assert "contentFrame.src = targetButton.dataset.viewPath ?? welcomePagePath" in body
    assert "contentFrame.addEventListener" in body
    assert "button.dataset.viewTarget" in body
    assert "button.dataset.viewPath" in body


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
    assert "syncSignedInAccount" in body
    assert 'window.sessionStorage.getItem(portalAccountStorageKey)?.trim() ?? ""' in body
    assert 'welcomeAccountDisplay.textContent = displayValue' in body
    assert "clearSignedInAccount" not in body
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
