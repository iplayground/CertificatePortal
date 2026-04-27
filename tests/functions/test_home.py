from __future__ import annotations

import azure.functions as func

from src.functions.assets import static_asset
from src.functions.home import home_page


def build_request(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    route_params: dict[str, str] | None = None,
) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url=url,
        headers=headers or {},
        params={},
        route_params=route_params or {},
        body=b"",
    )


def test_home_page_returns_html_with_expected_fields() -> None:
    response = home_page(build_request("http://localhost:7075/"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Vary"] == "Cookie, Accept-Language"
    assert "iPlayground 2026" not in body
    assert "iPlayground 2025" not in body
    assert "iPlayground 文件申請入口" in body
    assert "文件申請 - iPlayground" in body
    assert "報名人姓名" in body
    assert "會眾姓名" not in body
    assert "email" in body
    assert 'id="attendee-name"' in body
    assert 'id="email"' in body
    assert 'autocomplete="name"' not in body
    assert 'autocomplete="email"' not in body
    assert body.count('autocomplete="off"') == 2
    assert body.count('data-1p-ignore="true"') == 2
    assert body.count('data-op-ignore="true"') == 2
    assert body.count('data-lpignore="true"') == 2
    assert body.count('data-bwignore="true"') == 2
    assert body.count('data-protonpass-ignore="true"') == 2
    assert body.count('data-form-type="other"') == 2
    assert "請輸入您的報名人姓名" in body
    assert 'data-current-locale="zh-TW"' in body
    assert 'data-locale-cookie-name="ipg_locale"' in body
    assert 'id="locale-trigger"' in body
    assert 'id="locale-options"' in body
    assert 'id="home-page-i18n"' in body
    assert 'type="application/json"' in body
    assert '<span class="locale-trigger-icon" aria-hidden="true"></span>' in body
    assert 'data-locale="zh-TW"' in body
    assert 'data-locale="en-US"' in body
    assert "繁體中文" in body
    assert "English" in body
    assert "文件申請" in body
    assert "尚無可申請活動" in body
    assert "文件類型" in body
    assert "完訓證明" in body
    assert "營業稅繳稅證明" in body
    assert 'id="document-type-select"' in body
    assert 'id="document-type" name="documentType" type="hidden" value="completionCert"' in body
    assert 'data-value="completionCert"' in body
    assert 'data-label-key="document_type_completion_cert"' in body
    assert 'data-value="taxReceipt"' in body
    assert 'data-label-key="document_type_tax_receipt"' in body
    assert "本網站內容與相關資料之著作權均屬社團法人台北市頂尖軟體開發者協會(77212283)所有" in body
    assert "Azure Functions 線上頁面已啟用" not in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "iPlayground Certify" not in body
    assert 'class="custom-select-trigger"' in body
    assert 'id="event-name-trigger"' not in body
    assert 'id="event-name-options"' not in body
    assert 'class="field-static-value" id="event-name-value"' in body
    assert 'data-value="iPlayground 2025"' not in body
    assert 'name="viewport"' in body
    assert 'name="color-scheme"' in body
    assert 'name="theme-color"' in body
    assert 'name="robots"' in body
    assert 'name="application-name"' in body
    assert 'name="description"' in body
    assert 'property="og:url"' in body
    assert 'property="og:title"' in body
    assert 'property="og:description"' in body
    assert 'property="og:image"' in body
    assert 'name="twitter:card"' in body
    assert 'name="twitter:title"' not in body
    assert 'name="twitter:description"' not in body
    assert 'content="http://localhost:7075/"' in body
    assert 'content="http://localhost:7075/assets/logo_sq_b.png"' in body
    assert 'rel="canonical"' in body
    assert 'rel="icon"' in body
    assert 'href="/assets/favicon.png"' in body
    assert 'sizes="32x32"' in body
    assert 'href="/assets/logo_sq_b.png"' in body
    assert 'href="/assets/theme.css"' in body
    assert 'href="/assets/home.css"' in body
    assert 'src="/assets/home.js"' in body


def test_home_page_uses_accept_language_when_no_cookie_is_present() -> None:
    response = home_page(
        build_request(
            "http://localhost:7075/",
            headers={"Accept-Language": "en-US,en;q=0.9,zh;q=0.6"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "en-US"
    assert "<html lang=\"en-US\">" in body
    assert "Document Request - iPlayground" in body
    assert "iPlayground 2025" not in body
    assert "This page is currently a UI preview before the full flow is connected." in body
    assert "Registrant name" in body
    assert "Document type" in body
    assert "No available events" in body
    assert "Completion Certificate" in body
    assert "407 Tax Receipt" in body
    assert '<span id="document-type-value" class="custom-select-value">Completion Certificate</span>' in body
    assert "Submission flow not enabled yet" in body
    assert "Taipei Elite Software Developer Association (77212283)" in body
    assert "protected portal or lookup flow" in body
    assert 'data-current-locale="en-US"' in body
    assert "繁體中文" in body
    assert "English" in body


def test_home_page_prefers_forwarded_origin_for_head_urls() -> None:
    response = home_page(
        build_request(
            "http://127.0.0.1:7075/",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-Host": "certify.iplayground.test",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert 'rel="canonical" href="https://certify.iplayground.test/"' in body
    assert 'property="og:url" content="https://certify.iplayground.test/"' in body
    assert 'property="og:image" content="https://certify.iplayground.test/assets/logo_sq_b.png"' in body


def test_home_page_prefers_cookie_locale_over_accept_language() -> None:
    response = home_page(
        build_request(
            "http://localhost:7075/",
            headers={
                "Cookie": "ipg_locale=zh-TW",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "zh-TW"
    assert "文件申請" in body
    assert 'class="locale-menu-option is-current"' in body


def test_home_page_ignores_unsupported_cookie_locale_and_falls_back_to_accept_language() -> None:
    response = home_page(
        build_request(
            "http://localhost:7075/",
            headers={
                "Cookie": "ipg_locale=ja",
                "Accept-Language": "en-GB,en;q=0.9",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "en-US"
    assert "Attendee Information" in body


def test_home_page_maps_simplified_chinese_to_traditional_chinese_locale() -> None:
    response = home_page(
        build_request(
            "http://localhost:7075/",
            headers={"Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "zh-TW"
    assert "文件申請" in body


def test_home_css_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/home.css",
            route_params={"asset_name": "home.css"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert "@media (max-width: 640px)" in body
    assert ".custom-select-menu[hidden]" in body
    assert ".page-toolbar" in body
    assert "z-index: 4;" in body
    assert "body.is-locale-menu-open .hero-card > :not(.page-toolbar)" in body
    assert "width: max-content;" in body
    assert "white-space: nowrap;" in body
    assert ".locale-trigger" in body
    assert ".locale-menu-option" in body
    assert 'url("/assets/language_icon.svg")' in body
    assert "margin-inline: auto;" in body


def test_theme_css_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/theme.css",
            route_params={"asset_name": "theme.css"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert "color-scheme: light dark;" in body
    assert "@media (prefers-color-scheme: dark)" in body
    assert "repeating-linear-gradient" in body
    assert "--theme-primary-gradient" in body
    assert "linear-gradient(135deg, #5179fe 0%, #7f9aff 100%)" in body
    assert ".page-alert" in body
    assert ".page-alert-frame" in body
    assert ".page-alert-close" in body
    assert "@keyframes page-alert-dissolve" in body


def test_home_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/home.js",
            route_params={"asset_name": "home.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "previewAction.addEventListener" in body
    assert "parseHomePageI18n" in body
    assert "applyHomePageLocale" in body
    assert "closeEventNameSelect" in body
    assert "closeDocumentTypeSelect" in body
    assert "eventNameTrigger?.blur()" in body
    assert "canOpenEventNameSelect" in body
    assert "documentTypeTrigger.blur()" in body
    assert 'JSON.parse(homePageI18nScript.textContent ?? "{}")' in body
    assert "applyEventNameValue" in body
    assert "applyDocumentTypeValue" in body
    assert "updateDocumentTypeOptionLabels" in body
    assert "resolveDocumentTypeLabel" in body
    assert "setLocalePreference" in body
    assert "applyLocaleSelection" in body
    assert "localeOptions.forEach" in body
    assert "closeLocaleMenu" in body
    assert "document.title = homePageCopy.page_title" in body
    assert "htmlRoot.lang = bundle.html_lang" in body
    assert "updateMetaContent" in body
    assert "metaDescription" in body
    assert "metaOgLocale" in body
    assert "metaTwitterDescription" not in body
    assert 'homePage.classList.add("is-locale-menu-open")' in body
    assert 'homePage.classList.remove("is-locale-menu-open")' in body
    assert 'localeMenu?.addEventListener("pointerdown"' in body


def test_language_icon_svg_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/language_icon.svg",
            route_params={"asset_name": "language_icon.svg"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert "<svg" in body
    assert 'stroke="#0F172A"' in body


def test_logo_asset_returns_png_bytes() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/logo_b_alpha.png",
            route_params={"asset_name": "logo_b_alpha.png"},
        )
    )
    body = response.get_body()

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert body.startswith(b"\x89PNG")


def test_favicon_asset_returns_png_bytes() -> None:
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
