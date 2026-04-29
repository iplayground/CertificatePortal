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
    assert body == '{"document":{"status":"found","documentType":"completionCert"}}'


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
    assert body == '{"document":{"status":"found","documentType":"completionCert"}}'
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
    assert ".feedback.is-error" in body
    assert "var(--theme-feedback-error-color)" in body
    assert ".page-loading-overlay" in body
    assert "position: fixed;" in body
    assert "width: 100vw;" in body
    assert "min-height: 100vh;" in body
    assert "background: rgba(0, 0, 0, 0.64);" in body
    assert ".page-loading-panel" in body
    assert "background: #fff;" in body
    assert "@keyframes page-loading-spin" in body


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
    assert "previewAction.disabled = isLookupInProgress || !isUserDataComplete()" in body
    assert "setLookupBusy(true)" in body
    assert "setLookupBusy(false)" in body
    assert "pageLoadingOverlay.hidden = !isBusy" in body
    assert 'homePage.classList.toggle("is-lookup-busy", isBusy)' in body
    assert 'querySelectorAll("input, button, select, textarea")' in body
    assert "submitDocumentLookup" in body
    assert "fetch(documentLookupApiPath" in body
    assert "resolveLookupFailureMessage" in body
    assert "lookup_blocked" in body
    assert 'showLookupFeedback(resolveLookupFailureMessage(payload), "error")' in body
    assert 'showLookupFeedback(lookupUnavailableMessage, "error")' in body
    assert "lookupBlockedStorageKey" in body
    assert "lookupBlockedClientCacheMs = 60 * 60 * 1000" in body
    assert "readClientLookupBlockedUntil" in body
    assert "rememberClientLookupBlock" in body
    assert "window.localStorage.setItem" in body
    assert "window.localStorage.removeItem" in body
    assert "lookup_not_found_message" in body
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
