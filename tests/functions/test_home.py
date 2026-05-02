from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import azure.functions as func
import pytest

from src.functions.assets import static_asset
from src.functions.home import (
    build_document_lookup_blocked_message,
    home_page,
    public_completion_cert_change_request_api,
    public_document_lookup_api,
    public_events_list_api,
    resolve_public_lookup_client_ip,
)
from src.shared.event_store import EventStoreOperationError
from src.shared.public_lookup_store import (
    PublicLookupStoreOperationError,
    build_public_lookup_attempt_id,
    clear_public_lookup_local_block,
    remember_public_lookup_block,
)


@pytest.fixture(autouse=True)
def clear_public_lookup_cache() -> None:
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    clear_public_lookup_local_block(attempt_id=attempt_id)
    yield
    clear_public_lookup_local_block(attempt_id=attempt_id)


def build_request(
    url: str,
    *,
    method: str = "GET",
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
    route_params: dict[str, str] | None = None,
) -> func.HttpRequest:
    return func.HttpRequest(
        method=method,
        url=url,
        headers=headers or {},
        params=params or {},
        route_params=route_params or {},
        body=body,
    )


class FakeLookupAttemptsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.timeout_options: list[dict[str, Any]] = []

    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]:
        assert item == partition_key
        self.timeout_options.append(kwargs)
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error

        return self.items[item]

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        self.timeout_options.append(kwargs)
        self.items[body["id"]] = body
        return body


class FailingLookupAttemptsContainer(FakeLookupAttemptsContainer):
    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]:
        raise PublicLookupStoreOperationError("attempt store unavailable")

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise PublicLookupStoreOperationError("attempt store unavailable")


class FakeCompletionCertsContainer:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = items or []
        self.timeout_options: list[dict[str, Any]] = []

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        assert "SELECT TOP 1" in query
        assert "c.badgeName" in query
        assert "c.name" in query
        assert "c.organization" in query
        assert "LOWER(c.email)" not in query
        assert "AND c.number = @number" in query
        assert not enable_cross_partition_query
        self.timeout_options.append(kwargs)
        parameter_values = {
            parameter["name"]: parameter["value"]
            for parameter in parameters or []
        }
        assert partition_key == parameter_values["@eventId"]

        return [
            item
            for item in self.items
            if item["eventId"] == parameter_values["@eventId"]
            and item["number"] == parameter_values["@number"]
        ][:1]

    def read_item(self, item: str, partition_key: str, **_: Any) -> dict[str, Any]:
        for document in self.items:
            if document["id"] == item and document["eventId"] == partition_key:
                return document.copy()

        error = RuntimeError("not found")
        setattr(error, "status_code", 404)
        raise error

    def replace_item(self, item: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        for index, document in enumerate(self.items):
            if document["id"] == item:
                self.items[index] = body.copy()
                return self.items[index]

        error = RuntimeError("not found")
        setattr(error, "status_code", 404)
        raise error


class FakeCompletionCertRequestsContainer:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None) -> None:
        self.items: dict[str, dict[str, Any]] = items or {}

    def upsert_item(self, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        self.items[body["id"]] = body.copy()
        return self.items[body["id"]]

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        enable_cross_partition_query: bool,
        **_: Any,
    ) -> list[dict[str, Any]]:
        parameter_values = {parameter["name"]: parameter["value"] for parameter in parameters or []}
        completion_cert_id = parameter_values.get("@completionCertId")
        if completion_cert_id is None:
            return list(self.items.values())

        completed_statuses = {
            parameter_values.get("@approvedStatus"),
            parameter_values.get("@rejectedStatus"),
        }
        return [
            {
                "id": item["id"],
                "status": item.get("status"),
                "reviewedAt": item.get("reviewedAt"),
                "reviewNote": item.get("reviewNote"),
            }
            for item in sorted(
                self.items.values(),
                key=lambda candidate: str(candidate.get("reviewedAt", "")),
                reverse=True,
            )
            if item.get("completionCertId") == completion_cert_id
            and item.get("status") in completed_statuses
        ][:1]


class FakeEventsContainer:
    def __init__(self, items: dict[str, dict[str, Any]] | None = None) -> None:
        self.items = items or {
            "evt_1": {
                "id": "evt_1",
                "name": "iPlayground 2026",
                "status": "open",
                "documentTypes": ["completionCert"],
                "completionCertDownloadStartsAt": None,
            }
        }

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        assert item == partition_key
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error

        return self.items[item]

    def query_items(
        self,
        query: str,
        *,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, Any]]:
        return list(self.items.values())


@pytest.fixture(autouse=True)
def use_open_public_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.functions.home.get_events_container", lambda: FakeEventsContainer())


def build_document_lookup_request(
    *,
    body: dict[str, Any],
    ip_address: str = "203.0.113.10",
) -> func.HttpRequest:
    return build_request(
        "http://localhost:7075/api/v1/document-lookup",
        method="POST",
        body=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Forwarded-For": ip_address,
        },
    )


def build_completion_cert_change_request(
    *,
    body: dict[str, Any],
    headers: dict[str, str] | None = None,
) -> func.HttpRequest:
    return build_request(
        "http://localhost:7075/api/v1/completion-cert-change-requests",
        method="POST",
        body=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )


def test_resolve_public_lookup_client_ip_uses_forwarded_for() -> None:
    request = build_request(
        "http://localhost:7075/api/v1/document-lookup",
        headers={
            "X-Forwarded-For": "198.51.100.25, 10.0.0.1",
        },
    )

    assert resolve_public_lookup_client_ip(request) == "198.51.100.25"


def test_resolve_public_lookup_client_ip_removes_ipv4_port() -> None:
    request = build_request(
        "http://localhost:7075/api/v1/document-lookup",
        headers={
            "X-Forwarded-For": "198.51.100.25:54321, 10.0.0.1",
        },
    )

    assert resolve_public_lookup_client_ip(request) == "198.51.100.25"


def test_resolve_public_lookup_client_ip_removes_bracketed_ipv6_port() -> None:
    request = build_request(
        "http://localhost:7075/api/v1/document-lookup",
        headers={
            "X-Forwarded-For": "[2001:db8::25]:54321, 10.0.0.1",
        },
    )

    assert resolve_public_lookup_client_ip(request) == "2001:db8::25"


def test_resolve_public_lookup_client_ip_keeps_unbracketed_ipv6() -> None:
    request = build_request(
        "http://localhost:7075/api/v1/document-lookup",
        headers={
            "X-Forwarded-For": "2001:db8::25, 10.0.0.1",
        },
    )

    assert resolve_public_lookup_client_ip(request) == "2001:db8::25"


def test_resolve_public_lookup_client_ip_returns_none_without_forwarded_for() -> None:
    request = build_request("http://localhost:7075/api/v1/document-lookup")

    assert resolve_public_lookup_client_ip(request) is None


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
    assert "統編" in body
    assert "產製時間" in body
    assert "會眾姓名" not in body
    assert 'id="registration-number"' in body
    assert 'id="attendee-name"' not in body
    assert 'id="email"' in body
    assert 'id="business-tax-id"' in body
    assert 'id="generated-at"' in body
    assert 'class="form-datetime-input"' in body
    assert 'pattern="[0-9]{4} / [0-9]{2} / [0-9]{2} ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]"' in body
    assert (
        '<div class="field" id="registration-number-field" '
        'data-user-data-field data-document-types="completionCert" hidden>'
    ) in body
    assert 'id="attendee-name-field"' not in body
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
    assert 'data-lookup-pending-message="查詢中，請稍候。"' in body
    assert 'data-lookup-not-available-yet-message="完訓證明尚未開放下載，請於開放時間後再查詢。"' in body
    assert 'id="page-loading-overlay"' in body
    assert 'class="page-loading-panel"' in body
    assert 'class="page-loading-indicator"' in body
    assert '<div class="page-loading-text">查詢中，請稍候。</div>' in body
    assert 'autocomplete="name"' not in body
    assert 'autocomplete="email"' not in body
    assert body.count('autocomplete="off"') == 4
    assert body.count('data-1p-ignore="true"') == 4
    assert body.count('data-op-ignore="true"') == 4
    assert body.count('data-lpignore="true"') == 4
    assert body.count('data-bwignore="true"') == 4
    assert body.count('data-protonpass-ignore="true"') == 4
    assert body.count('data-form-type="other"') == 4
    assert "請輸入報名序號" in body
    assert "請輸入統一編號" in body
    assert "---- / -- / -- --:--:--" in body
    assert 'data-current-locale="zh-TW"' in body
    assert 'data-locale-cookie-name="ipg_locale"' in body
    assert 'data-certificate-change-request-api-path="/api/v1/completion-cert-change-requests"' in body
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
    assert "選擇證明顯示方式" in body
    assert "一旦確認後，將無法更改" in body
    assert "姓名顯示方式" in body
    assert "顯示公司名：{organization}" in body
    assert "提出修改申請" in body
    assert 'id="certificate-change-request-action"' in body
    assert 'id="certificate-change-request-processing-feedback"' in body
    assert "若現在產生證書，將視為放棄本次修改申請。" in body
    assert "修改申請" in body
    assert "請描述需要調整的證明資料" in body
    assert 'id="certificate-change-request-view" hidden tabindex="-1"' in body
    assert 'id="certificate-change-request-form"' in body
    assert 'id="certificate-change-request-event-value"' in body
    assert 'id="certificate-change-request-registration-number-value"' in body
    assert 'id="certificate-change-request-email-value"' in body
    assert 'id="certificate-change-request-current-name-value"' not in body
    assert 'id="certificate-change-request-note"' in body
    assert 'class="form-textarea"' in body
    assert 'class="form-textarea-shell certificate-change-request-textarea-shell"' in body
    assert 'maxlength="600"' in body
    assert "例如：想改成本名，或公司名需要調整。" in body
    assert "Badge Name 應改為" not in body
    assert "請只填寫必要的更正內容" in body
    assert "返回顯示方式" in body
    assert "送出申請" in body
    assert "修改申請已送出，管理者確認後會再處理發證。" in body
    assert "產生證書" in body
    assert 'id="certificate-generate-action"' in body
    assert 'id="certificate-options-step-label"' not in body
    assert 'id="certificate-options-view" hidden tabindex="-1"' in body
    assert 'id="certificate-name-options"' in body
    assert 'id="certificate-company-visible" type="checkbox"' in body
    assert "返回查詢" in body
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
    assert 'id="attendee-name"' not in body
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
    assert "Choose Certificate Display" in body
    assert "Once confirmed, it cannot be changed." in body
    assert "Name display" in body
    assert "Show company name: {organization}" in body
    assert "Generate Certificate" in body
    assert "Back to Search" in body
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


def test_public_document_lookup_api_returns_generic_failure_and_records_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "missing@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 404
    assert response.mimetype == "application/json"
    assert '"code":"document_not_found"' in body
    assert "查不到符合條件的文件" in body
    assert "email" not in body.lower()
    assert "registration" not in body.lower()
    assert len(attempts_container.items) == 1
    assert next(iter(attempts_container.items.values()))["failureCount"] == 1
    assert next(iter(attempts_container.items.values()))["blockedUntil"] is None


def test_public_document_lookup_api_skips_attempt_record_without_forwarded_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(),
    )

    response = public_document_lookup_api(
        build_request(
            "http://localhost:7075/api/v1/document-lookup",
            method="POST",
            body=json.dumps(
                {
                    "documentType": "completionCert",
                    "eventId": "evt_1",
                    "registrationNumber": "100",
                    "email": "missing@example.com",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 404
    assert '"code":"document_not_found"' in body
    assert attempts_container.items == {}


def test_public_document_lookup_api_blocks_completion_lookup_before_download_opens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_events_container",
        lambda: FakeEventsContainer(
            {
                "evt_1": {
                    "id": "evt_1",
                    "name": "iPlayground 2026",
                    "status": "open",
                    "documentTypes": ["completionCert"],
                    "completionCertDownloadStartsAt": "2999-04-27T12:38:00Z",
                }
            }
        ),
    )

    def fail_if_querying_completion_records() -> object:
        raise AssertionError("unavailable certificates should not query completion records")

    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        fail_if_querying_completion_records,
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 403
    assert '"code":"document_not_available_yet"' in body
    assert "完訓證明尚未開放下載" in body
    attempt_document = next(iter(attempts_container.items.values()))
    assert attempt_document["notAvailableCount"] == 1
    assert attempt_document["blockedUntil"] is None


def test_public_document_lookup_api_blocks_ip_after_tenth_unavailable_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_events_container",
        lambda: FakeEventsContainer(
            {
                "evt_1": {
                    "id": "evt_1",
                    "name": "iPlayground 2026",
                    "status": "open",
                    "documentTypes": ["completionCert"],
                    "completionCertDownloadStartsAt": "2999-04-27T12:38:00Z",
                }
            }
        ),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(),
    )

    responses = [
        public_document_lookup_api(
            build_document_lookup_request(
                body={
                    "documentType": "completionCert",
                    "eventId": "evt_1",
                    "registrationNumber": "100",
                    "email": "ming@example.com",
                },
            )
        )
        for _ in range(10)
    ]
    blocked_body = responses[-1].get_body().decode("utf-8")
    attempt_document = next(iter(attempts_container.items.values()))

    assert [response.status_code for response in responses] == [403] * 9 + [429]
    assert '"code":"lookup_blocked"' in blocked_body
    assert "暫停查詢 12 小時" in blocked_body
    assert attempt_document["notAvailableCount"] == 10
    assert attempt_document["blockedUntil"] is not None


def test_public_document_lookup_api_blocks_ip_after_fifth_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(),
    )

    responses = [
        public_document_lookup_api(
            build_document_lookup_request(
                body={
                    "documentType": "completionCert",
                    "eventId": "evt_1",
                    "registrationNumber": "100",
                    "email": "missing@example.com",
                },
            )
        )
        for _ in range(5)
    ]
    blocked_body = responses[-1].get_body().decode("utf-8")
    attempt_document = next(iter(attempts_container.items.values()))

    assert [response.status_code for response in responses] == [404, 404, 404, 404, 429]
    assert '"code":"lookup_blocked"' in blocked_body
    assert "暫停查詢 24 小時" in blocked_body
    assert "IP" not in blocked_body
    assert "剩" not in blocked_body
    assert attempt_document["ipAddress"] == "203.0.113.10"
    assert attempt_document["failureCount"] == 5
    assert attempt_document["blockedUntil"] is not None


def test_build_document_lookup_blocked_message_uses_remaining_hours() -> None:
    message = build_document_lookup_blocked_message(
        {"blockedUntil": "2999-04-29T00:04:00Z"}
    )

    assert message.startswith("查詢失敗次數過多，已暫停查詢 ")
    assert message.endswith(" 小時。")
    assert "IP" not in message


def test_build_document_lookup_blocked_message_uses_ceiled_minutes_under_one_hour() -> None:
    blocked_until = (datetime.now(timezone.utc) + timedelta(minutes=12, seconds=1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    message = build_document_lookup_blocked_message({"blockedUntil": blocked_until})

    assert message == "查詢失敗次數過多，已暫停查詢 13 分鐘。"


def test_build_document_lookup_blocked_message_uses_one_minute_under_one_minute() -> None:
    blocked_until = (datetime.now(timezone.utc) + timedelta(seconds=30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    message = build_document_lookup_blocked_message({"blockedUntil": blocked_until})

    assert message == "查詢失敗次數過多，已暫停查詢 1 分鐘。"


def test_public_document_lookup_api_keeps_blocked_ip_from_querying(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    attempts_container.items[attempt_id] = {
        "id": attempt_id,
        "ipAddress": "203.0.113.10",
        "failureCount": 5,
        "firstFailedAt": "2026-04-29T00:00:00Z",
        "lastFailedAt": "2026-04-29T00:04:00Z",
        "blockedUntil": "2999-04-29T00:04:00Z",
        "updatedAt": "2026-04-29T00:04:00Z",
    }

    def fail_if_querying_completion_records() -> object:
        raise AssertionError("blocked IP should not query completion records")

    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        fail_if_querying_completion_records,
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 429
    assert '"code":"lookup_blocked"' in body


def test_public_document_lookup_api_does_not_block_on_attempt_store_read_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "missing@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 404
    assert '"code":"document_not_found"' in body


def test_public_document_lookup_api_does_not_block_success_on_attempt_store_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "issued",
                    "issuedPdfBlobName": "issued/ccert_1.pdf",
                }
            ]
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":false,'
        '"certStatus":"issued","name":"王小明",'
        '"organization":"iPlayground"}}'
    )


def test_public_document_lookup_api_marks_not_generated_completion_cert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "notIssued",
                    "issuedPdfBlobName": None,
                }
            ]
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":true,'
        '"certStatus":"notIssued","name":"王小明",'
        '"organization":"iPlayground"}}'
    )


def test_public_document_lookup_api_marks_completed_change_request_as_not_requestable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "notIssued",
                    "issuedPdfBlobName": None,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_cert_requests_container",
        lambda: FakeCompletionCertRequestsContainer(
            {
                "ccreq_1": {
                    "id": "ccreq_1",
                    "completionCertId": "ccert_1",
                    "eventId": "evt_1",
                    "status": "approved",
                    "requesterEmail": "ming@example.com",
                    "requesterNote": "想改成本名",
                    "reviewedBy": "admin@iplayground.io",
                    "reviewedAt": "2026-04-30T08:30:00Z",
                    "reviewCompletedNotifiedAt": None,
                    "reviewNote": "已修正",
                    "createdAt": "2026-04-30T08:00:00Z",
                    "updatedAt": "2026-04-30T08:30:00Z",
                }
            }
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":false,'
        '"certStatus":"notIssued","name":"王小明",'
        '"organization":"iPlayground",'
        '"changeRequestReview":{"status":"approved",'
        '"reviewedAt":"2026-04-30T08:30:00Z","reviewNote":"已修正"}}}'
    )


def test_public_document_lookup_api_returns_rejected_change_request_review_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "notIssued",
                    "issuedPdfBlobName": None,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_cert_requests_container",
        lambda: FakeCompletionCertRequestsContainer(
            {
                "ccreq_1": {
                    "id": "ccreq_1",
                    "completionCertId": "ccert_1",
                    "eventId": "evt_1",
                    "status": "rejected",
                    "requesterEmail": "ming@example.com",
                    "requesterNote": "想改成本名",
                    "reviewedBy": "admin@iplayground.io",
                    "reviewedAt": "2026-04-30T08:30:00Z",
                    "reviewCompletedNotifiedAt": None,
                    "reviewNote": "資料不符",
                    "createdAt": "2026-04-30T08:00:00Z",
                    "updatedAt": "2026-04-30T08:30:00Z",
                }
            }
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":false,'
        '"certStatus":"notIssued","name":"王小明",'
        '"organization":"iPlayground",'
        '"changeRequestReview":{"status":"rejected",'
        '"reviewedAt":"2026-04-30T08:30:00Z","reviewNote":"資料不符"}}}'
    )


def test_public_document_lookup_api_returns_change_requested_cert_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: FailingLookupAttemptsContainer(),
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "changeRequested",
                    "issuedPdfBlobName": None,
                }
            ]
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":false,'
        '"certStatus":"changeRequested","name":"王小明",'
        '"organization":"iPlayground"}}'
    )


def test_public_completion_cert_change_request_api_writes_request_and_updates_cert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certs_container = FakeCompletionCertsContainer(
        [
            {
                "id": "ccert_1",
                "eventId": "evt_1",
                "number": 100,
                "email": "Ming@example.com",
                "badgeName": "Ming",
                "name": "王小明",
                "organization": "iPlayground",
                "certStatus": "notIssued",
                "issuedPdfBlobName": None,
            }
        ]
    )
    requests_container = FakeCompletionCertRequestsContainer()
    monkeypatch.setattr("src.functions.home.get_completion_records_container", lambda: certs_container)
    monkeypatch.setattr(
        "src.functions.home.get_completion_cert_requests_container",
        lambda: requests_container,
    )

    response = public_completion_cert_change_request_api(
        build_completion_cert_change_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
                "requesterNote": "想改成本名",
            },
        )
    )
    body = response.get_body().decode("utf-8")
    request_document = next(iter(requests_container.items.values()))

    assert response.status_code == 201
    assert response.mimetype == "application/json"
    assert '"status":"pending"' in body
    assert '"completionCertId":"ccert_1"' in body
    assert request_document["completionCertId"] == "ccert_1"
    assert request_document["eventId"] == "evt_1"
    assert request_document["requesterEmail"] == "ming@example.com"
    assert request_document["requesterNote"] == "想改成本名"
    assert certs_container.items[0]["certStatus"] == "changeRequested"
    assert certs_container.items[0]["updatedAt"] == request_document["updatedAt"]


def test_public_completion_cert_change_request_api_is_idempotent_for_same_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certs_container = FakeCompletionCertsContainer(
        [
            {
                "id": "ccert_1",
                "eventId": "evt_1",
                "number": 100,
                "email": "Ming@example.com",
                "badgeName": "Ming",
                "name": "王小明",
                "organization": "iPlayground",
                "certStatus": "notIssued",
                "issuedPdfBlobName": None,
            }
        ]
    )
    requests_container = FakeCompletionCertRequestsContainer()
    monkeypatch.setattr("src.functions.home.get_completion_records_container", lambda: certs_container)
    monkeypatch.setattr(
        "src.functions.home.get_completion_cert_requests_container",
        lambda: requests_container,
    )
    request = build_completion_cert_change_request(
        body={
            "documentType": "completionCert",
            "eventId": "evt_1",
            "registrationNumber": "100",
            "email": "ming@example.com",
            "requesterNote": "想改成本名",
        },
    )

    first_response = public_completion_cert_change_request_api(request)
    second_response = public_completion_cert_change_request_api(request)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert len(requests_container.items) == 1


def test_public_completion_cert_change_request_api_rejects_after_completed_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    certs_container = FakeCompletionCertsContainer(
        [
            {
                "id": "ccert_1",
                "eventId": "evt_1",
                "number": 100,
                "email": "Ming@example.com",
                "badgeName": "Ming",
                "name": "王小明",
                "organization": "iPlayground",
                "certStatus": "notIssued",
                "issuedPdfBlobName": None,
            }
        ]
    )
    requests_container = FakeCompletionCertRequestsContainer(
        {
            "ccreq_1": {
                "id": "ccreq_1",
                "completionCertId": "ccert_1",
                "eventId": "evt_1",
                "status": "rejected",
                "requesterEmail": "ming@example.com",
                "requesterNote": "想改成本名",
                "reviewedBy": "admin@iplayground.io",
                "reviewedAt": "2026-04-30T08:30:00Z",
                "reviewCompletedNotifiedAt": None,
                "reviewNote": "資料不符",
                "createdAt": "2026-04-30T08:00:00Z",
                "updatedAt": "2026-04-30T08:30:00Z",
            }
        }
    )
    monkeypatch.setattr("src.functions.home.get_completion_records_container", lambda: certs_container)
    monkeypatch.setattr(
        "src.functions.home.get_completion_cert_requests_container",
        lambda: requests_container,
    )

    response = public_completion_cert_change_request_api(
        build_completion_cert_change_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
                "requesterNote": "想改公司名",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 409
    assert '"code":"change_request_not_allowed"' in body
    assert len(requests_container.items) == 1
    assert certs_container.items[0]["certStatus"] == "notIssued"


def test_public_completion_cert_change_request_api_rejects_cross_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_querying_completion_records() -> object:
        raise AssertionError("cross-origin request should not query completion records")

    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        fail_if_querying_completion_records,
    )

    response = public_completion_cert_change_request_api(
        build_completion_cert_change_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
                "requesterNote": "想改成本名",
            },
            headers={"Origin": "https://evil.example"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 403
    assert '"code":"same_origin_required"' in body


def test_public_completion_cert_change_request_api_rejects_invalid_payload() -> None:
    response = public_completion_cert_change_request_api(
        build_completion_cert_change_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
                "requesterNote": "",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert '"code":"invalid_change_request"' in body


def test_public_completion_cert_change_request_api_rejects_issued_cert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "issued",
                    "issuedPdfBlobName": "issued/ccert_1.pdf",
                }
            ]
        ),
    )

    response = public_completion_cert_change_request_api(
        build_completion_cert_change_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
                "requesterNote": "想改公司名",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 409
    assert '"code":"change_request_not_allowed"' in body


def test_public_document_lookup_api_uses_local_block_cache_before_cosmos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    remember_public_lookup_block(
        attempt_id=attempt_id,
        attempt_document={
            "id": attempt_id,
            "blockedUntil": "2999-04-29T00:04:00Z",
        },
    )

    def fail_if_querying_lookup_attempts() -> object:
        raise AssertionError("locally cached block should not query Cosmos")

    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        fail_if_querying_lookup_attempts,
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 429
    assert '"code":"lookup_blocked"' in body


def test_public_document_lookup_api_resets_failures_after_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts_container = FakeLookupAttemptsContainer()
    attempts_container.upsert_item(
        {
            "id": build_public_lookup_attempt_id("203.0.113.10"),
            "ipAddress": "203.0.113.10",
            "failureCount": 3,
            "firstFailedAt": "2026-04-29T00:00:00Z",
            "lastFailedAt": "2026-04-29T00:03:00Z",
            "blockedUntil": None,
            "updatedAt": "2026-04-29T00:03:00Z",
        }
    )
    monkeypatch.setattr(
        "src.functions.home.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    monkeypatch.setattr(
        "src.functions.home.get_completion_records_container",
        lambda: FakeCompletionCertsContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 100,
                    "email": "Ming@example.com",
                    "badgeName": "Ming",
                    "name": "王小明",
                    "organization": "iPlayground",
                    "certStatus": "issued",
                    "issuedPdfBlobName": "issued/ccert_1.pdf",
                }
            ]
        ),
    )

    response = public_document_lookup_api(
        build_document_lookup_request(
            body={
                "documentType": "completionCert",
                "eventId": "evt_1",
                "registrationNumber": "100",
                "email": "ming@example.com",
            },
        )
    )
    body = response.get_body().decode("utf-8")
    attempt_document = next(iter(attempts_container.items.values()))

    assert response.status_code == 200
    assert body == (
        '{"document":{"status":"found","documentType":"completionCert",'
        '"badgeName":"Ming","canRequestChanges":false,'
        '"certStatus":"issued","name":"王小明",'
        '"organization":"iPlayground"}}'
    )
    assert attempt_document["ipAddress"] == "203.0.113.10"
    assert attempt_document["failureCount"] == 0
    assert attempt_document["blockedUntil"] is None


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
    assert ".page-toolbar" in body
    assert "z-index: 4;" in body
    assert "body.is-locale-menu-open .hero-card > :not(.page-toolbar)" in body
    assert "width: max-content;" in body
    assert "white-space: nowrap;" in body
    assert ".locale-trigger" in body
    assert ".locale-menu-option" in body
    assert 'url("/assets/language_icon.svg")' in body
    assert "margin-inline: auto;" in body
    assert ".feedback.is-error" in body
    assert "var(--theme-feedback-error-color)" in body
    assert "white-space: pre-line;" in body
    assert ".page-loading-overlay" in body
    assert "position: fixed;" in body
    assert "width: 100vw;" in body
    assert "min-height: 100vh;" in body
    assert "background: rgba(0, 0, 0, 0.64);" in body
    assert ".page-loading-panel" in body
    assert "background: #fff;" in body
    assert "@keyframes page-loading-spin" in body
    assert ".certificate-options-view" in body
    assert ".certificate-change-request-view" in body
    assert ".certificate-summary-list" in body
    assert ".certificate-change-request-form textarea" not in body
    assert ".form-textarea" in body
    assert ".certificate-choice-option" in body
    assert '.certificate-choice-option input[type="radio"]' in body
    assert ".certificate-choice-option span::before" in body
    assert "width: 12px;" in body
    assert "height: 12px;" in body
    assert "border: 1.5px solid #111827;" in body
    assert '.certificate-choice-option input[type="radio"]:checked + span::before' in body
    assert ".certificate-company-option" in body
    assert '.certificate-company-option input[type="checkbox"]' in body
    assert "min-height: 0;" in body
    assert '.certificate-company-option input[type="checkbox"]:focus-visible' in body
    assert ".certificate-actions" in body
    assert ".certificate-change-request-action" in body
    assert "margin-left: auto;" in body
    assert "form.is-certificate-options-active .field-static-value" in body
    assert "cursor: not-allowed;" in body


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
    assert ".custom-select-menu[hidden]" in body
    assert ".custom-select-trigger[hidden]" in body
    assert ".field-static-value[hidden]" in body
    assert ".custom-select-trigger:disabled" in body
    assert ".secondary-action" in body
    assert ".brand-square-action" in body
    assert "--theme-icon-square-color: #ee5fa7;" in body
    assert "--theme-icon-square-gradient: linear-gradient(135deg, #ee5fa7 0%, #ff8fc6 100%);" in body
    assert "--theme-icon-square-shadow: rgba(238, 95, 167, 0.26);" in body
    assert ".form-checkbox-option" in body
    assert "accent-color: var(--theme-accent-deep);" in body
    assert "accent-color: #ea6e1e;" in body
    assert "color-scheme: light;" in body
    assert "grid-template-columns: 22px minmax(0, 1fr);" in body
    assert ".form-datetime-input" in body
    assert ".form-textarea" in body
    assert ".form-textarea-shell" in body
    assert ".form-textarea::placeholder" in body
    assert ".form-textarea:focus" in body
    assert ".form-datetime-picker" in body
    assert ".form-datetime-picker:focus-within" in body
    assert ".form-datetime-picker-date-native:focus" in body
    assert ".form-datetime-picker-date" in body
    assert ".form-datetime-picker-time" in body
    assert "grid-template-columns: minmax(26px, 30px) max-content minmax(26px, 30px) max-content minmax(26px, 30px);" in body


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
    assert "previewAction.disabled = isLookupInProgress || !isUserDataComplete()" in body
    assert "setLookupBusy(true)" in body
    assert "setLookupBusy(false)" in body
    assert "pageLoadingOverlay.hidden = !isBusy" in body
    assert 'homePage.classList.toggle("is-lookup-busy", isBusy)' in body
    assert 'querySelectorAll("input, button, select, textarea")' in body
    assert "submitDocumentLookup" in body
    assert "clearLookupFeedback" in body
    assert "shouldShowCertificateOptions" in body
    assert "setDocumentLookupFieldsLocked" in body
    assert 'documentRequestForm.classList.toggle("is-certificate-options-active", isLocked)' in body
    assert "buildCertificateNameChoices" in body
    assert "showCertificateOptions" in body
    assert '["notIssued", "changeRequested"].includes(documentData?.certStatus)' in body
    assert "renderCertificateOptionsStatus" in body
    assert "certificateChangeRequestProcessingFeedback" in body
    assert "documentData?.canRequestChanges" in body
    assert "certificateChangeRequestAction.hidden = !canRequestChanges" in body
    assert "certificateOptionsChangeRequestStatus?.message" in body
    assert "documentData?.changeRequestReview?.status" in body
    assert "certificate_change_request_approved_message" in body
    assert "certificate_change_request_rejected_message" in body
    assert "completedReviewTone = \"error\"" in body
    assert "changeRequestReview?.reviewNote" in body
    assert "審核備註：" in body
    assert "certificateChangeRequestProcessingFeedback.hidden = !statusMessage" in body
    assert "setCertificateOptionsChangeRequestStatus(message, \"success\")" in body
    assert "setCertificateOptionsChangeRequestStatus(errorMessage, \"error\")" in body
    assert "currentCertificateDocument.canRequestChanges = false" in body
    assert "showCertificateChangeRequest" in body
    assert "showCertificateOptionsFromChangeRequest" in body
    assert "renderCertificateOptionsStatus(currentCertificateDocument)" in body
    assert "renderCertificateChangeRequestSummary" in body
    assert "updateCertificateChangeRequestSubmitState" in body
    assert "isChangeRequestSubmitted" in body
    assert "setChangeRequestSubmitted(true)" in body
    assert 'certificateChangeRequestNote.disabled = isSubmitted' in body
    assert 'currentCertificateDocument.certStatus === "changeRequested"' in body
    assert "showDocumentLookupForm" in body
    assert "certificateCompanyVisible.checked = Boolean(organization)" in body
    assert "previewAction.hidden = isLocked" in body
    assert "certificateChangeRequestAction" in body
    assert "certificateChangeRequestForm?.addEventListener" in body
    assert "certificateChangeRequestApiPath" in body
    assert "submitCertificateChangeRequest" in body
    assert "fetch(certificateChangeRequestApiPath" in body
    assert "certificate_change_request_submitted_message" in body
    assert "certificate_change_request_unavailable_message" in body
    assert "certificateGenerateAction" in body
    assert "certificateNameDisplay" in body
    assert "nameWithBadge" in body
    assert "fetch(documentLookupApiPath" in body
    assert "resolveLookupFailureMessage" in body
    assert "lookup_blocked" in body
    assert "document_not_available_yet" in body
    assert 'showLookupFeedback(resolveLookupFailureMessage(payload), "error")' in body
    assert "successfulDocument = payload?.document ?? {}" in body
    assert "showCertificateOptions(successfulDocument)" in body
    assert "clearLookupFeedback()" in body
    assert 'showLookupFeedback(lookupUnavailableMessage, "error")' in body
    assert "submitDocumentLookupFromCompletionCertInput" in body
    assert 'event.key !== "Enter" || event.isComposing' in body
    assert "[registrationNumber, email].filter(Boolean).forEach" in body
    assert 'input.addEventListener("keydown", submitDocumentLookupFromCompletionCertInput)' in body
    assert "lookupBlockedStorageKey" in body
    assert "lookupBlockedClientCacheMs = 60 * 60 * 1000" in body
    assert "readClientLookupBlockedUntil" in body
    assert "rememberClientLookupBlock" in body
    assert "window.localStorage.setItem" in body
    assert "window.localStorage.removeItem" in body
    assert "lookup_not_found_message" in body
    assert "lookup_not_available_yet_message" in body
    assert "lookup_pending_message" in body
    assert "[registrationNumber, attendeeName, email, businessTaxId, generatedAt].filter(Boolean).forEach" in body
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
