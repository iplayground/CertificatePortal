from __future__ import annotations

import azure.functions as func
import pytest

from src.functions.assets import static_asset
from src.functions.home import home_page, public_events_list_api
from src.shared.event_store import EventStoreOperationError


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
    assert "報名序號" in body
    assert "報名人姓名" in body
    assert "統編" in body
    assert "產製時間" in body
    assert "會眾姓名" not in body
    assert 'id="registration-number"' in body
    assert 'id="attendee-name"' in body
    assert 'id="email"' in body
    assert 'id="business-tax-id"' in body
    assert 'id="generated-at"' in body
    assert 'class="form-datetime-input"' in body
    assert 'pattern="[0-9]{4} / [0-9]{2} / [0-9]{2} ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"' in body
    assert (
        '<div class="field" id="registration-number-field" '
        'data-user-data-field data-document-types="completionCert" hidden>'
    ) in body
    assert (
        '<div class="field" id="attendee-name-field" '
        'data-user-data-field data-document-types="completionCert" hidden>'
    ) in body
    assert (
        '<div class="field" id="email-field" '
        'data-user-data-field data-document-types="completionCert" hidden>'
    ) in body
    assert (
        '<div class="field" id="business-tax-id-field" '
        'data-user-data-field data-document-types="taxReceipt" hidden>'
    ) in body
    assert (
        '<div class="field" id="generated-at-field" '
        'data-user-data-field data-document-types="taxReceipt" hidden>'
    ) in body
    assert '<button class="primary-action" type="button" id="preview-action" disabled>查詢文件</button>' in body
    assert 'autocomplete="name"' not in body
    assert 'autocomplete="email"' not in body
    assert body.count('autocomplete="off"') == 5
    assert body.count('data-1p-ignore="true"') == 5
    assert body.count('data-op-ignore="true"') == 5
    assert body.count('data-lpignore="true"') == 5
    assert body.count('data-bwignore="true"') == 5
    assert body.count('data-protonpass-ignore="true"') == 5
    assert body.count('data-form-type="other"') == 5
    assert "請輸入報名序號" in body
    assert "請輸入您的報名人姓名" in body
    assert "請輸入統一編號" in body
    assert "---- / -- / -- --:--:--" in body
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
    assert "請選擇目前開放申請的活動，查詢可申請的文件。" in body
    assert "請先選擇您要申請的活動與文件類型。" in body
    assert "填寫報名人姓名與 email" not in body
    assert "活動載入中" in body
    assert "尚無可申請活動" in body
    assert "文件類型" in body
    assert "文件類型載入中" in body
    assert "尚無可申請文件" in body
    assert "完訓證明" in body
    assert "營業稅繳稅證明" in body
    assert "查詢文件" in body
    assert "請確認填寫資訊與報名資料一致。" not in body
    assert "選擇活動與文件類型後，填寫報名人姓名與 email。" not in body
    assert "若查詢不到資料" not in body
    assert '<div class="field" id="document-type-field" hidden>' in body
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
    assert 'src="/assets/portal-datetime-picker.js"' in body
    assert 'src="/assets/home.js"' in body
    assert body.index('src="/assets/portal-datetime-picker.js"') < body.index('src="/assets/home.js"')


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
    assert "currently open events" in body
    assert "Choose the event and document type for your request." in body
    assert "then enter the registrant name and email" not in body
    assert "Registration number" in body
    assert "Registrant name" in body
    assert "Tax ID" in body
    assert "Generated at" in body
    assert "Document type" in body
    assert "Loading document types" in body
    assert "No available documents" in body
    assert "Loading events" in body
    assert "No available events" in body
    assert "Completion Certificate" in body
    assert "407 Tax Receipt" in body
    assert '<div class="field" id="document-type-field" hidden>' in body
    assert '<span id="document-type-value" class="custom-select-value">Loading document types</span>' in body
    assert "Look Up Documents" in body
    assert "Make sure the information matches the registration record." not in body
    assert "Taipei Elite Software Developer Association (77212283)" in body
    assert "If no record is found" not in body
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


def test_home_page_renders_open_events_from_event_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_home_page_queries_events() -> object:
        raise AssertionError("home page should not synchronously query Cosmos DB")

    monkeypatch.setattr("src.functions.home.get_events_container", fail_if_home_page_queries_events)

    response = home_page(build_request("http://localhost:7075/"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert 'data-events-api-path="/api/v1/events"' in body
    assert 'id="event-name-control"' in body
    assert 'id="event-name-trigger"' not in body
    assert "iPlayground 2026" not in body
    assert 'value="completionCert"' in body
    assert 'data-value="taxReceipt"' in body


def test_home_page_renders_static_document_type_when_selected_event_has_one_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_home_page_queries_events() -> object:
        raise AssertionError("home page should not synchronously query Cosmos DB")

    monkeypatch.setattr("src.functions.home.get_events_container", fail_if_home_page_queries_events)

    response = home_page(build_request("http://localhost:7075/"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '<div class="field" id="document-type-field" hidden>' in body
    assert '<div class="field-static-value" id="document-type-static-value" hidden>文件類型載入中</div>' in body
    assert 'id="document-type-trigger"' in body
    assert 'value="completionCert"' in body
    assert 'data-value="taxReceipt"' in body


def test_home_page_ignores_event_store_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.home.get_events_container", lambda: object())

    def raise_event_store_error(**_: object) -> list[dict[str, object]]:
        raise EventStoreOperationError("event store unavailable")

    monkeypatch.setattr("src.functions.home.list_public_event_documents", raise_event_store_error)

    response = home_page(build_request("http://localhost:7075/"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "活動載入中" in body
    assert 'id="event-name-trigger"' not in body


def test_public_events_list_api_allows_anonymous_cross_origin_reads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.home.get_events_container", lambda: object())
    monkeypatch.setattr(
        "src.functions.home.list_public_event_documents",
        lambda **_: [
            {
                "id": "evt_2026",
                "name": "iPlayground 2026",
                "status": "open",
                "documentTypes": ["completionCert", "taxReceipt"],
                "createdBy": "admin@iplayground.io",
                "updatedBy": "admin@iplayground.io",
            },
            {
                "id": "evt_hidden",
                "name": "Broken Event",
                "documentTypes": [],
            },
        ],
    )

    response = public_events_list_api(
        build_request(
            "http://localhost:7075/api/v1/events",
            headers={"Origin": "https://third-party.example"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.headers["Cache-Control"] == "no-store"
    assert body == (
        '{"events":[{"id":"evt_2026","name":"iPlayground 2026",'
        '"documentTypes":["completionCert","taxReceipt"]},'
        '{"id":"evt_hidden","name":"Broken Event","documentTypes":[]}]}'
    )
    assert "admin@iplayground.io" not in body


def test_public_events_list_api_returns_json_error_when_event_store_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.home.get_events_container", lambda: object())

    def raise_event_store_error(**_: object) -> list[dict[str, object]]:
        raise EventStoreOperationError("event store unavailable")

    monkeypatch.setattr("src.functions.home.list_public_event_documents", raise_event_store_error)

    response = public_events_list_api(build_request("http://localhost:7075/api/v1/events"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 503
    assert response.mimetype == "application/json"
    assert '"code":"event_store_unavailable"' in body


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
    assert "Request Information" in body


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
    assert ".custom-select-trigger[hidden]" in body
    assert ".field-static-value[hidden]" in body
    assert ".page-toolbar" in body
    assert "z-index: 4;" in body
    assert "body.is-locale-menu-open .hero-card > :not(.page-toolbar)" in body
    assert "width: max-content;" in body
    assert "white-space: nowrap;" in body
    assert ".locale-trigger" in body
    assert ".locale-menu-option" in body
    assert ".form-datetime-input" in body
    assert ".form-datetime-picker" in body
    assert "grid-template-columns: max-content max-content;" in body
    assert "justify-content: start;" in body
    assert ".form-datetime-picker:focus-within" in body
    assert ".form-datetime-picker-date-native:focus" in body
    assert "box-sizing: border-box;" in body
    assert ".form-datetime-picker-date" in body
    assert ".form-datetime-picker-time" in body
    assert "grid-template-columns: minmax(26px, 30px) max-content minmax(26px, 30px) max-content minmax(26px, 30px);" in body
    assert "border-radius: 0;" in body
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
    assert "loadHomeEvents" in body
    assert "fetch(eventsApiPath" in body
    assert "renderHomeEvents" in body
    assert "renderMultipleEventControl" in body
    assert "setDocumentTypeFieldVisible" in body
    assert "documentTypeField.hidden = !isVisible" in body
    assert "getVisibleUserDataInputs" in body
    assert "updateUserDataFieldsForDocumentType" in body
    assert "isUserDataComplete" in body
    assert "updatePreviewActionState" in body
    assert "previewAction.disabled = !isUserDataComplete()" in body
    assert "[registrationNumber, attendeeName, email, businessTaxId, generatedAt].forEach" in body
    assert 'input.addEventListener("input", updatePreviewActionState)' in body
    assert "installDateTimePicker" in body
    assert "window.iPlaygroundPortalDateTime" in body
    assert "installDateTimePicker(generatedAt, { includeSeconds: true })" in body
    assert "event_name_loading_option" in body
    assert "document_type_loading_option" in body
    assert "document_type_empty_option" in body
    assert "applyDocumentTypeLoadingState" in body
    assert "syncCurrentEventMetadata" in body
    assert "eventNameInput.dataset.eventDocumentTypes" in body
    assert "applyAvailableDocumentTypes(getSelectedEventDocumentTypes(normalizedValue))" in body
    assert "updateDocumentTypeControlMode" in body
    assert "documentTypeTrigger.hidden = useStaticValue" in body
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
