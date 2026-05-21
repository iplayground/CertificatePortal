from __future__ import annotations

import base64
import io
import json
import zipfile
from http.cookies import SimpleCookie
from typing import Any

import azure.functions as func
import pytest

from src.functions.assets import static_asset
from src.functions.portal import (
    PORTAL_GOOGLE_LOGIN_NOT_AUTHORIZED_ERROR,
    build_portal_csrf_token,
    is_valid_tax_receipt_download_ticket,
    portal_admin_dashboard_welcome_metrics_api,
    portal_admin_completion_certs_import_api,
    portal_admin_completion_certs_list_api,
    portal_admin_completion_certs_update_api,
    portal_admin_completion_cert_change_requests_list_api,
    portal_admin_completion_cert_change_requests_review_api,
    portal_admin_events_create_api,
    portal_admin_events_update_api,
    portal_admin_tax_receipts_list_create_api,
    portal_admin_tax_receipts_update_delete_api,
    public_tax_receipts_download_api,
    portal_dashboard_completion_reviews_page,
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
from src.shared.portal_auth import resolve_portal_access
from src.shared.tax_receipt_download_ticket import build_tax_receipt_download_ticket
from src.shared.event_store import EventStoreOperationError
from src.shared.portal_google_group_auth import PortalGoogleGroupAuthorizationError
from src.shared.public_lookup_store import (
    build_public_lookup_attempt_id,
    clear_public_lookup_local_block,
)


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


class FakeEventsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def create_item(self, body: dict[str, Any]) -> dict[str, Any]:
        self.items[body["id"]] = body
        return body

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        assert item == partition_key
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        return self.items[item]

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        assert item == body["id"]
        self.items[item] = body
        return body


class FakeCompletionCertsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        document = self.items.get(item)
        if document is None or document["eventId"] != partition_key:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        return document

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        self.items[item] = body
        return body

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        self.items[body["id"]] = body
        return body

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, Any]]:
        assert "WHERE c.eventId = @eventId" in query
        assert not enable_cross_partition_query
        event_id = next(
            parameter["value"]
            for parameter in parameters or []
            if parameter["name"] == "@eventId"
        )
        assert partition_key == event_id
        return sorted(
            [
                item
                for item in self.items.values()
                if item["eventId"] == event_id
            ],
            key=lambda item: item["number"],
        )


class FakeCompletionCertRequestsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        document = self.items.get(item)
        if document is None or document["eventId"] != partition_key:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        return document

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        self.items[item] = body
        return body

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        self.items[body["id"]] = body
        return body

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        enable_cross_partition_query: bool,
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        assert "WHERE c.status = @status" in query
        assert enable_cross_partition_query
        status = next(
            parameter["value"]
            for parameter in parameters or []
            if parameter["name"] == "@status"
        )
        return [
            item
            for item in self.items.values()
            if item["status"] == status
        ]


class FakeTaxReceiptsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}
        self.query_count = 0

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        document = self.items.get(item)
        if document is None or document["eventId"] != partition_key:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        return document

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        self.items[item] = body
        return body

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        self.items[body["id"]] = body
        return body

    def delete_item(self, item: str, partition_key: str) -> None:
        document = self.items.get(item)
        if document is None or document["eventId"] != partition_key:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error
        del self.items[item]

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        enable_cross_partition_query: bool,
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        self.query_count += 1
        assert "WHERE c.eventId = @eventId" in query
        assert not enable_cross_partition_query
        event_id = next(
            parameter["value"]
            for parameter in parameters or []
            if parameter["name"] == "@eventId"
        )
        assert partition_key == event_id
        return sorted(
            [
                item
                for item in self.items.values()
                if item["eventId"] == event_id
            ],
            key=lambda item: item["generatedAt"],
            reverse=True,
        )


class FakeLookupAttemptsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def read_item(self, item: str, partition_key: str, **_: Any) -> dict[str, Any]:
        assert item == partition_key
        if item not in self.items:
            error = RuntimeError("not found")
            setattr(error, "status_code", 404)
            raise error

        return self.items[item]

    def upsert_item(self, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        self.items[body["id"]] = body
        return body


def build_authorized_portal_api_request(
    monkeypatch: pytest.MonkeyPatch,
    *,
    body: bytes = b"",
    method: str = "POST",
    origin: str = "http://localhost:7075",
    params: dict[str, str] | None = None,
    url: str = "http://localhost:7075/api/v1/admin/events",
    route_params: dict[str, str] | None = None,
) -> func.HttpRequest:
    configure_portal_auth_bypass_env(monkeypatch)
    token_request = build_request("http://localhost:7075/portal/dashboard")
    token = build_portal_csrf_token(token_request, resolve_portal_access(token_request))
    return build_request(
        url,
        method=method,
        body=body,
        headers={
            "Content-Type": "application/json",
            "Host": "localhost:7075",
            "Idempotency-Key": "event-create-test-key",
            "Origin": origin,
            "X-Portal-CSRF-Token": token,
        },
        params=params,
        route_params=route_params,
    )


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


def test_portal_admin_events_create_api_requires_authenticated_portal_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)

    response = portal_admin_events_create_api(
        build_request(
            "http://localhost:7075/api/v1/admin/events",
            method="POST",
            body=b"{}",
            headers={
                "Host": "localhost:7075",
                "Origin": "http://localhost:7075",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 401
    assert response.mimetype == "application/json"
    assert "unauthorized" in body


def test_portal_admin_events_create_api_rejects_cross_origin_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=b"{}",
        origin="https://attacker.example",
    )

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 403
    assert "invalid_origin" in body


def test_portal_admin_events_create_api_rejects_missing_csrf_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_admin_events_create_api(
        build_request(
            "http://localhost:7075/api/v1/admin/events",
            method="POST",
            body=b"{}",
            headers={
                "Host": "localhost:7075",
                "Idempotency-Key": "event-create-test-key",
                "Origin": "http://localhost:7075",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 403
    assert "invalid_csrf_token" in body


def test_portal_admin_events_create_api_creates_event_with_utc_iso_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_container = FakeEventsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"iPlayground 2026","status":"unlisted",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":16,'
            b'"documentTypes":["completionCert"],'
            b'"completionCertDownloadStartsAt":"2026-04-27T12:38:00Z"}'
        ),
    )

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 201
    assert '"event"' in body
    assert len(fake_container.items) == 1
    event = next(iter(fake_container.items.values()))
    assert event["id"].startswith("evt_")
    assert event["name"] == "iPlayground 2026"
    assert event["status"] == "unlisted"
    assert event["documentTypes"] == ["completionCert"]
    assert event["eventStartDate"] == "2026-07-24"
    assert event["eventEndDate"] == "2026-07-25"
    assert event["completionHours"] == 16
    assert event["completionCertDownloadStartsAt"] == "2026-04-27T12:38:00Z"
    assert event["createdBy"] == "admin@iplayground.io"
    assert event["updatedBy"] == "admin@iplayground.io"


def test_portal_admin_events_create_api_allows_non_completion_event_without_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_container = FakeEventsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"iPlayground 2026","status":"open",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":null,'
            b'"documentTypes":["taxReceipt"],'
            b'"completionCertDownloadStartsAt":""}'
        ),
    )

    response = portal_admin_events_create_api(request)

    assert response.status_code == 201
    event = next(iter(fake_container.items.values()))
    assert event["documentTypes"] == ["taxReceipt"]
    assert event["completionHours"] is None
    assert event["completionCertDownloadStartsAt"] is None


def test_portal_admin_events_create_api_preserves_completion_settings_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_container = FakeEventsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"iPlayground 2026","status":"open",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":16,'
            b'"documentTypes":["taxReceipt"],'
            b'"completionCertDownloadStartsAt":"2026-04-27T12:38:00Z"}'
        ),
    )

    response = portal_admin_events_create_api(request)

    assert response.status_code == 201
    event = next(iter(fake_container.items.values()))
    assert event["documentTypes"] == ["taxReceipt"]
    assert event["completionHours"] == 16
    assert event["completionCertDownloadStartsAt"] == "2026-04-27T12:38:00Z"


def test_portal_admin_events_create_api_rejects_local_display_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"iPlayground 2026","status":"open",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":16,'
            b'"documentTypes":["completionCert"],'
            b'"completionCertDownloadStartsAt":"2026 / 04 / 27 20:38"}'
        ),
    )

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert "UTC ISO 8601" in body


def test_portal_admin_events_create_api_returns_json_when_event_store_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)

    def raise_event_store_error(**_: Any) -> tuple[dict[str, Any], bool]:
        raise EventStoreOperationError("Cosmos DB 活動容器不存在。")

    monkeypatch.setattr("src.functions.portal.create_event_document", raise_event_store_error)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"iPlayground 2026","status":"unlisted",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":16,'
            b'"documentTypes":["completionCert"],'
            b'"completionCertDownloadStartsAt":"2026-04-27T12:38:00Z"}'
        ),
    )

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 503
    assert response.mimetype == "application/json"
    assert "event_store_unavailable" in body


def test_portal_admin_events_update_api_updates_existing_event_without_creating_duplicate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_container = FakeEventsContainer()
    fake_container.items["evt_existing"] = {
        "id": "evt_existing",
        "name": "Old Event",
        "status": "unlisted",
        "documentTypes": ["completionCert"],
        "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
        "createdAt": "2026-04-27T12:00:00Z",
        "createdBy": "creator@example.com",
        "updatedAt": "2026-04-27T12:00:00Z",
        "updatedBy": "creator@example.com",
    }
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=(
            b'{"name":"Updated Event","status":"open",'
            b'"eventStartDate":"2026-07-24","eventEndDate":"2026-07-25",'
            b'"completionHours":16,'
            b'"documentTypes":["taxReceipt"],'
            b'"completionCertDownloadStartsAt":null}'
        ),
        method="PUT",
        route_params={"event_id": "evt_existing"},
        url="http://localhost:7075/api/v1/admin/events/evt_existing",
    )

    response = portal_admin_events_update_api(request)
    event = fake_container.items["evt_existing"]

    assert response.status_code == 200
    assert len(fake_container.items) == 1
    assert event["id"] == "evt_existing"
    assert event["name"] == "Updated Event"
    assert event["status"] == "open"
    assert event["documentTypes"] == ["taxReceipt"]
    assert event["eventStartDate"] == "2026-07-24"
    assert event["eventEndDate"] == "2026-07-25"
    assert event["completionHours"] == 16
    assert event["completionCertDownloadStartsAt"] is None
    assert event["createdAt"] == "2026-04-27T12:00:00Z"
    assert event["createdBy"] == "creator@example.com"
    assert event["updatedBy"] == "admin@iplayground.io"


def test_portal_admin_events_list_api_returns_events_without_blocking_page_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    monkeypatch.setattr(
        "src.functions.portal.list_event_documents",
        lambda **_: [
            {
                "id": "evt_1",
                "name": "iPlayground 2026",
                "status": "open",
                "documentTypes": ["completionCert", "taxReceipt"],
                "eventStartDate": "2026-07-24",
                "eventEndDate": "2026-07-25",
                "completionHours": 16,
                "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
                "createdAt": "2026-04-27T12:00:00Z",
            }
        ],
    )
    request = build_authorized_portal_api_request(monkeypatch, method="GET")

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert '"events"' in body
    assert '"name":"iPlayground 2026"' in body
    assert '"status":"open"' in body
    assert '"documentTypes":["completionCert","taxReceipt"]' in body
    assert '"eventStartDate":"2026-07-24"' in body
    assert '"eventEndDate":"2026-07-25"' in body
    assert '"completionHours":16' in body
    assert '"completionCertDownloadStartsAt":"2026-04-27T12:38:00Z"' in body


def test_portal_admin_events_list_api_includes_unlisted_and_non_completion_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    monkeypatch.setattr(
        "src.functions.portal.list_event_documents",
        lambda **_: [
            {
                "id": "evt_unlisted",
                "name": "下架活動",
                "status": "unlisted",
                "documentTypes": ["taxReceipt"],
                "eventStartDate": "2026-07-24",
                "eventEndDate": "2026-07-25",
                "completionHours": 16,
                "completionCertDownloadStartsAt": "",
            },
            {
                "id": "evt_open",
                "name": "開放活動",
                "status": "open",
                "documentTypes": [],
                "eventStartDate": "2026-07-24",
                "eventEndDate": "2026-07-25",
                "completionHours": 16,
                "completionCertDownloadStartsAt": "",
            },
        ],
    )
    request = build_authorized_portal_api_request(monkeypatch, method="GET")

    response = portal_admin_events_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"id":"evt_unlisted"' in body
    assert '"name":"下架活動"' in body
    assert '"status":"unlisted"' in body
    assert '"documentTypes":["taxReceipt"]' in body
    assert '"id":"evt_open"' in body
    assert '"name":"開放活動"' in body


def test_portal_admin_completion_certs_import_api_writes_kktix_csv_to_cosmos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_1"] = {
        "id": "evt_1",
        "name": "iPlayground 2026",
    }
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": (
                    "不需要欄位,Email,你是誰，ID 或具有鑑識度的名稱 Name on Badge,"
                    "票種,Id,報名序號,姓名 Full Name,"
                    "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n"
                    "ignore,ming@example.com,Ming,一般票,KKTIX-001,1,,iPlayground"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"summary":{"imported":1}' in body
    assert len(fake_completion_container.items) == 1
    completion_cert = next(iter(fake_completion_container.items.values()))
    assert completion_cert["id"].startswith("ccert_")
    assert completion_cert["eventId"] == "evt_1"
    assert completion_cert["number"] == 1
    assert completion_cert["ticketName"] == "一般票"
    assert completion_cert["name"] == ""
    assert completion_cert["organization"] == "iPlayground"
    assert completion_cert["email"] == "ming@example.com"
    assert completion_cert["kktixId"] == "KKTIX-001"
    assert completion_cert["badgeName"] == "Ming"
    assert completion_cert["attendanceStatus"] == "notCheckedIn"
    assert completion_cert["certStatus"] == "notIssued"
    assert completion_cert["issuedPdfBlobName"] is None
    assert completion_cert["verificationTokenHash"] is None
    assert completion_cert["verificationCount"] == 0
    assert completion_cert["issuedAt"] is None
    assert "不需要欄位" not in completion_cert


def test_portal_admin_completion_certs_import_api_allows_empty_optional_csv_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_1"] = {
        "id": "evt_1",
        "name": "iPlayground 2026",
    }
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": (
                    "Email,你是誰，ID 或具有鑑識度的名稱 Name on Badge,"
                    "票種,Id,報名序號,姓名 Full Name,"
                    "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n"
                    "ming@example.com,Ming,一般票,KKTIX-001,1,,"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)

    assert response.status_code == 200
    completion_cert = next(iter(fake_completion_container.items.values()))
    assert completion_cert["name"] == ""
    assert completion_cert["organization"] == ""


def test_portal_admin_completion_certs_import_api_uses_field_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_1"] = {
        "id": "evt_1",
        "name": "iPlayground 2026",
    }
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": (
                    "序號,信箱,暱稱,姓名,公司,KKTIX代碼,票券\n"
                    "8,lin@example.com,Lin Badge,林小美,iPlayground,KKTIX-008,工作坊票"
                ),
                "fieldMapping": {
                    "number": 0,
                    "email": 1,
                    "badgeName": 2,
                    "name": 3,
                    "organization": 4,
                    "kktixId": 5,
                    "ticketName": 6,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)

    assert response.status_code == 200
    completion_cert = next(iter(fake_completion_container.items.values()))
    assert completion_cert["number"] == 8
    assert completion_cert["email"] == "lin@example.com"
    assert completion_cert["badgeName"] == "Lin Badge"
    assert completion_cert["name"] == "林小美"
    assert completion_cert["organization"] == "iPlayground"
    assert completion_cert["kktixId"] == "KKTIX-008"
    assert completion_cert["ticketName"] == "工作坊票"


def test_portal_admin_completion_certs_import_api_rejects_unknown_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_missing",
                "csvText": (
                    "報名序號,票種,Email,Id,"
                    "你是誰，ID 或具有鑑識度的名稱 Name on Badge,"
                    "姓名 Full Name,"
                    "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n"
                    "1,一般票,ming@example.com,KKTIX-001,Ming,,"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 404
    assert "event_not_found" in body


def test_portal_admin_completion_certs_import_api_rejects_missing_required_csv_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": "報名序號,Email\nREG-001,ming@example.com",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert "CSV 缺少必要欄位：Badge Name、Id、姓名 Full Name、公司名、票種" in body


def test_portal_admin_completion_certs_import_api_rejects_missing_required_csv_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": (
                    "報名序號,票種,姓名 Full Name,Email,Id,"
                    "你是誰，ID 或具有鑑識度的名稱 Name on Badge,"
                    "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n"
                    "REG-001,,王小明,,KKTIX-001,Ming,\n"
                    "REG-002,一般票,,hui@example.com,,,"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    payload = json.loads(body)
    assert payload["error"]["message"] == "CSV 有 2 筆資料需要修正，尚未匯入 DB。"
    assert payload["error"]["details"]["rowErrors"] == [
        {
            "rowNumber": 2,
            "fields": ["Email", "票種"],
            "message": "CSV 第 2 列缺少必要欄位值：Email、票種。",
        },
        {
            "rowNumber": 3,
            "fields": ["Badge Name", "Id"],
            "message": "CSV 第 3 列缺少必要欄位值：Badge Name、Id。",
        },
    ]
    assert fake_completion_container.items == {}


def test_portal_admin_completion_certs_import_api_rejects_non_integer_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "csvText": (
                    "報名序號,票種,Email,Id,"
                    "你是誰，ID 或具有鑑識度的名稱 Name on Badge,"
                    "姓名 Full Name,"
                    "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)\n"
                    "REG-001,一般票,ming@example.com,KKTIX-001,Ming,,"
                ),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/completion-certs/import",
    )

    response = portal_admin_completion_certs_import_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    payload = json.loads(body)
    assert payload["error"]["details"]["rowErrors"] == [
        {
            "rowNumber": 2,
            "fields": ["報名序號"],
            "message": "CSV 第 2 列報名序號必須是整數。",
        },
    ]
    assert fake_completion_container.items == {}


def test_portal_admin_completion_certs_list_api_returns_event_partition_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_2"] = {
        "id": "ccert_2",
        "eventId": "evt_1",
        "number": 2,
        "kktixId": "KKTIX-002",
        "badgeName": "",
        "ticketName": "一般票",
        "name": "王小華",
        "organization": "好玩公司",
        "email": "hua@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "notIssued",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        method="GET",
        url="http://localhost:7075/api/v1/admin/completion-certs",
        params={"eventId": "evt_1"},
    )

    response = portal_admin_completion_certs_list_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"completionCerts"' in body
    assert '"number":2' in body
    assert '"organization":"好玩公司"' in body
    assert '"attendanceStatus":"checkedIn"' in body
    assert '"verificationCount":0' in body


def test_portal_admin_completion_certs_update_api_updates_mutable_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_2"] = {
        "id": "ccert_2",
        "eventId": "evt_1",
        "number": 2,
        "kktixId": "KKTIX-002",
        "badgeName": "Old Badge",
        "ticketName": "一般票",
        "name": "王小華",
        "organization": "舊公司",
        "email": "hua@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "notIssued",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "attendanceStatus": "notCheckedIn",
                "eventId": "evt_1",
                "badgeName": "New Badge",
                "email": "new@example.com",
                "name": "",
                "organization": "新公司",
                "number": 999,
                "ticketName": "VIP",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"certid": "ccert_2"},
        url="http://localhost:7075/api/v1/admin/completion-certs/ccert_2",
    )

    response = portal_admin_completion_certs_update_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"completionCert"' in body
    assert fake_completion_container.items["ccert_2"]["number"] == 2
    assert fake_completion_container.items["ccert_2"]["kktixId"] == "KKTIX-002"
    assert fake_completion_container.items["ccert_2"]["badgeName"] == "Old Badge"
    assert fake_completion_container.items["ccert_2"]["email"] == "new@example.com"
    assert fake_completion_container.items["ccert_2"]["name"] == ""
    assert fake_completion_container.items["ccert_2"]["organization"] == "新公司"
    assert fake_completion_container.items["ccert_2"]["attendanceStatus"] == "notCheckedIn"
    assert fake_completion_container.items["ccert_2"]["ticketName"] == "一般票"


def test_portal_admin_completion_certs_update_api_rejects_invalid_attendance_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_2"] = {
        "id": "ccert_2",
        "eventId": "evt_1",
        "number": 2,
        "kktixId": "KKTIX-002",
        "badgeName": "Old Badge",
        "ticketName": "一般票",
        "name": "王小華",
        "organization": "舊公司",
        "email": "hua@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "notIssued",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "attendanceStatus": "maybe",
                "eventId": "evt_1",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"certid": "ccert_2"},
        url="http://localhost:7075/api/v1/admin/completion-certs/ccert_2",
    )

    response = portal_admin_completion_certs_update_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert "簽到狀態不合法" in body
    assert fake_completion_container.items["ccert_2"]["attendanceStatus"] == "checkedIn"


def test_portal_admin_completion_certs_update_api_rejects_empty_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "email": "",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"certid": "ccert_2"},
        url="http://localhost:7075/api/v1/admin/completion-certs/ccert_2",
    )

    response = portal_admin_completion_certs_update_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert "完訓證明資料缺少必要欄位值：Email" in body


def test_portal_admin_tax_receipts_create_api_writes_metadata_to_cosmos_and_file_to_blob(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_tax"] = {
        "id": "evt_tax",
        "name": "營業稅活動",
        "documentTypes": ["taxReceipt"],
    }
    fake_tax_container = FakeTaxReceiptsContainer()
    uploaded_blobs: dict[str, dict[str, Any]] = {}
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.upload_blob_bytes",
        lambda *, blob_name, container_name, content_type, data: uploaded_blobs.setdefault(
            blob_name,
            {
                "containerName": container_name,
                "contentType": content_type,
                "data": data,
            },
        ),
    )
    file_bytes = b"%PDF-1.4 tax receipt"
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_tax",
                "taxId": "12345678",
                "amount": 186000,
                "generatedAt": "2026-05-13T15:00:44Z",
                "fileName": "receipt.pdf",
                "contentType": "application/pdf",
                "fileBase64": base64.b64encode(file_bytes).decode("ascii"),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/tax-receipts",
    )

    response = portal_admin_tax_receipts_list_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 201
    payload = json.loads(body)
    assert payload["taxReceipt"]["id"].startswith("trec_")
    assert "downloadUrl" not in payload["taxReceipt"]
    assert len(fake_tax_container.items) == 1
    receipt = next(iter(fake_tax_container.items.values()))
    assert receipt["eventId"] == "evt_tax"
    assert receipt["taxId"] == "12345678"
    assert receipt["amount"] == 186000
    assert receipt["generatedAt"] == "2026-05-13T15:00:44Z"
    assert receipt["fileName"] == "receipt-12345678-1.pdf"
    assert receipt["fileSequence"] == 1
    assert receipt["contentType"] == "application/pdf"
    assert receipt["fileSize"] == len(file_bytes)
    assert receipt["sourceBlobName"] == f"evt_tax/{receipt['id']}.pdf"
    assert receipt["downloadCount"] == 0
    assert receipt["portalDownloadCount"] == 0
    assert uploaded_blobs[receipt["sourceBlobName"]] == {
        "containerName": "tax-receipts",
        "contentType": "application/pdf",
        "data": file_bytes,
    }


def test_portal_admin_tax_receipts_create_api_rejects_decimal_amount(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_tax",
                "taxId": "12345678",
                "amount": "186000.5",
                "generatedAt": "2026-05-13T15:00:44Z",
                "fileName": "receipt.pdf",
                "contentType": "application/pdf",
                "fileBase64": base64.b64encode(b"%PDF-1.4").decode("ascii"),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/tax-receipts",
    )

    response = portal_admin_tax_receipts_list_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 400
    assert "金額必須是大於 0 的整數" in body


def test_portal_admin_tax_receipts_create_api_uses_next_tax_id_file_sequence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_tax"] = {
        "id": "evt_tax",
        "name": "營業稅活動",
        "documentTypes": ["taxReceipt"],
    }
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_existing"] = {
        "id": "trec_existing",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 100,
        "generatedAt": "2026-05-13T15:00:00Z",
        "sourceBlobName": "evt_tax/trec_existing.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 8,
        "downloadCount": 0,
        "createdAt": "2026-05-13T15:00:00Z",
        "updatedAt": "2026-05-13T15:00:00Z",
    }
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.upload_blob_bytes",
        lambda *, blob_name, container_name, content_type, data: None,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_tax",
                "taxId": "12345678",
                "amount": 186000,
                "generatedAt": "2026-05-13T15:00:44Z",
                "fileName": "receipt.pdf",
                "contentType": "application/pdf",
                "fileBase64": base64.b64encode(b"%PDF-1.4").decode("ascii"),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        url="http://localhost:7075/api/v1/admin/tax-receipts",
    )

    response = portal_admin_tax_receipts_list_create_api(request)

    assert response.status_code == 201
    created_receipt = [
        item
        for item in fake_tax_container.items.values()
        if item["id"] != "trec_existing"
    ][0]
    assert created_receipt["fileName"] == "receipt-12345678-2.pdf"
    assert created_receipt["fileSequence"] == 2


def test_portal_admin_tax_receipts_list_api_reads_event_partition_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 186000,
        "generatedAt": "2026-05-13T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 8,
        "downloadCount": 0,
        "createdAt": "2026-05-13T15:01:00Z",
        "updatedAt": "2026-05-13T15:01:00Z",
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        method="GET",
        url="http://localhost:7075/api/v1/admin/tax-receipts",
        params={"eventId": "evt_tax"},
    )

    response = portal_admin_tax_receipts_list_create_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    payload = json.loads(body)
    assert payload["taxReceipts"][0]["id"] == "trec_1"
    assert payload["taxReceipts"][0]["amount"] == 186000
    assert "downloadUrl" not in payload["taxReceipts"][0]


def test_portal_admin_tax_receipts_update_api_updates_cosmos_and_replaces_blob(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_tax"] = {
        "id": "evt_tax",
        "name": "營業稅活動",
        "documentTypes": ["taxReceipt"],
    }
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 186000,
        "generatedAt": "2026-05-13T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 8,
        "downloadCount": 0,
        "createdAt": "2026-05-13T15:01:00Z",
        "updatedAt": "2026-05-13T15:01:00Z",
    }
    uploaded_blobs: dict[str, dict[str, Any]] = {}
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.upload_blob_bytes",
        lambda *, blob_name, container_name, content_type, data: uploaded_blobs.setdefault(
            blob_name,
            {
                "containerName": container_name,
                "contentType": content_type,
                "data": data,
            },
        ),
    )
    replacement_bytes = b"\x89PNG\r\n"
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_tax",
                "taxId": "12345678",
                "amount": "187,000",
                "generatedAt": "2026-05-13T15:02:05Z",
                "fileName": "receipt.png",
                "contentType": "image/png",
                "fileBase64": base64.b64encode(replacement_bytes).decode("ascii"),
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"receiptid": "trec_1"},
        url="http://localhost:7075/api/v1/admin/tax-receipts/trec_1",
    )

    response = portal_admin_tax_receipts_update_delete_api(request)

    assert response.status_code == 200
    receipt = fake_tax_container.items["trec_1"]
    assert receipt["taxId"] == "12345678"
    assert receipt["amount"] == 187000
    assert receipt["generatedAt"] == "2026-05-13T15:02:05Z"
    assert receipt["fileName"] == "receipt-12345678-1.png"
    assert receipt["fileSequence"] == 1
    assert receipt["contentType"] == "image/png"
    assert receipt["sourceBlobName"] == "evt_tax/trec_1.png"
    assert fake_tax_container.query_count == 0
    assert uploaded_blobs["evt_tax/trec_1.png"] == {
        "containerName": "tax-receipts",
        "contentType": "image/png",
        "data": replacement_bytes,
    }


def test_portal_admin_tax_receipts_update_api_rejects_tax_id_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_events_container = FakeEventsContainer()
    fake_events_container.items["evt_tax"] = {
        "id": "evt_tax",
        "name": "營業稅活動",
        "documentTypes": ["taxReceipt"],
    }
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 186000,
        "generatedAt": "2026-05-13T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 8,
        "downloadCount": 0,
        "createdAt": "2026-05-13T15:01:00Z",
        "updatedAt": "2026-05-13T15:01:00Z",
    }
    monkeypatch.setattr("src.functions.portal.get_events_container", lambda: fake_events_container)
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_tax",
                "taxId": "87654321",
                "amount": "187000",
                "generatedAt": "2026-05-13T15:02:05Z",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"receiptid": "trec_1"},
        url="http://localhost:7075/api/v1/admin/tax-receipts/trec_1",
    )

    response = portal_admin_tax_receipts_update_delete_api(request)

    assert response.status_code == 400
    payload = json.loads(response.get_body())
    assert payload["error"]["code"] == "tax_receipt_tax_id_immutable"
    assert payload["error"]["message"] == "統編不可在編輯時修改。請刪除後重新新增。"
    assert fake_tax_container.items["trec_1"]["taxId"] == "12345678"
    assert fake_tax_container.items["trec_1"]["amount"] == 186000


def test_portal_admin_tax_receipts_delete_api_removes_cosmos_document_and_blob(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
    }
    deleted_blobs: list[tuple[str, str]] = []
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.delete_blob",
        lambda *, blob_name, container_name: deleted_blobs.append((container_name, blob_name)),
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        method="DELETE",
        params={"eventId": "evt_tax"},
        route_params={"receiptid": "trec_1"},
        url="http://localhost:7075/api/v1/admin/tax-receipts/trec_1",
    )

    response = portal_admin_tax_receipts_update_delete_api(request)

    assert response.status_code == 200
    assert fake_tax_container.items == {}
    assert deleted_blobs == [("tax-receipts", "evt_tax/trec_1.pdf")]


def test_public_tax_receipts_download_api_rejects_request_without_portal_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_request(
        "http://localhost:7075/api/v1/tax-receipts/download",
        body=json.dumps({"eventId": "evt_tax", "receiptIds": ["trec_1"]}).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Host": "localhost:7075",
            "Origin": "http://localhost:7075",
        },
        method="POST",
    )

    response = public_tax_receipts_download_api(request)

    assert response.status_code == 403
    assert "invalid_tax_receipt_download_authorization" in response.get_body().decode("utf-8")


def test_public_tax_receipts_download_api_blocks_ip_after_fifth_invalid_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    attempts_container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.25")
    clear_public_lookup_local_block(attempt_id=attempt_id)
    monkeypatch.setattr(
        "src.functions.portal.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )
    request_body = json.dumps(
        {"eventId": "evt_tax", "receiptIds": ["trec_1"], "downloadTicket": "invalid"}
    ).encode("utf-8")

    try:
        responses = [
            public_tax_receipts_download_api(
                build_request(
                    "http://localhost:7075/api/v1/tax-receipts/download",
                    body=request_body,
                    headers={
                        "Content-Type": "application/json",
                        "Host": "localhost:7075",
                        "Origin": "http://localhost:7075",
                        "X-Forwarded-For": "203.0.113.25",
                    },
                    method="POST",
                )
            )
            for _ in range(5)
        ]
    finally:
        clear_public_lookup_local_block(attempt_id=attempt_id)

    blocked_body = responses[-1].get_body().decode("utf-8")
    attempt_document = attempts_container.items[attempt_id]

    assert [response.status_code for response in responses] == [403, 403, 403, 403, 429]
    assert '"code":"lookup_blocked"' in blocked_body
    assert "暫停查詢 24 小時" in blocked_body
    assert attempt_document["ipAddress"] == "203.0.113.25"
    assert attempt_document["failureCount"] == 5
    assert attempt_document["blockedUntil"] is not None


def test_public_tax_receipts_download_api_keeps_blocked_ip_from_downloading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    attempts_container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.25")
    attempts_container.items[attempt_id] = {
        "id": attempt_id,
        "ipAddress": "203.0.113.25",
        "failureCount": 5,
        "firstFailedAt": "2026-04-29T00:00:00Z",
        "lastFailedAt": "2026-04-29T00:04:00Z",
        "blockedUntil": "2999-04-29T00:04:00Z",
        "updatedAt": "2026-04-29T00:04:00Z",
    }
    clear_public_lookup_local_block(attempt_id=attempt_id)
    monkeypatch.setattr(
        "src.functions.portal.get_public_lookup_attempts_container",
        lambda: attempts_container,
    )

    try:
        response = public_tax_receipts_download_api(
            build_request(
                "http://localhost:7075/api/v1/tax-receipts/download",
                body=json.dumps(
                    {"eventId": "evt_tax", "receiptIds": ["trec_1"], "downloadTicket": "invalid"}
                ).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Host": "localhost:7075",
                    "Origin": "http://localhost:7075",
                    "X-Forwarded-For": "203.0.113.25",
                },
                method="POST",
            )
        )
    finally:
        clear_public_lookup_local_block(attempt_id=attempt_id)

    body = response.get_body().decode("utf-8")

    assert response.status_code == 429
    assert '"code":"lookup_blocked"' in body
    assert "invalid_tax_receipt_download_authorization" not in body


def test_public_tax_receipts_download_api_rejects_invalid_download_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=b"not-json",
        method="POST",
        url="http://localhost:7075/api/v1/tax-receipts/download",
    )

    response = public_tax_receipts_download_api(request)

    assert response.status_code == 400
    assert "invalid_tax_receipt_download_payload" in response.get_body().decode("utf-8")


def test_public_tax_receipts_download_api_downloads_blob_with_portal_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.download_blob_bytes",
        lambda *, blob_name, container_name: b"%PDF-1.4"
        if (container_name, blob_name) == ("tax-receipts", "evt_tax/trec_1.pdf")
        else b"",
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps({"eventId": "evt_tax", "receiptIds": ["trec_1"]}).encode("utf-8"),
        method="POST",
        url="http://localhost:7075/api/v1/tax-receipts/download",
    )

    response = public_tax_receipts_download_api(request)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="receipt-12345678-1.pdf"'
    )
    assert response.get_body() == b"%PDF-1.4"
    assert fake_tax_container.items["trec_1"].get("downloadCount", 0) == 0
    assert "lastDownloadAt" not in fake_tax_container.items["trec_1"]
    assert fake_tax_container.items["trec_1"]["portalDownloadCount"] == 1
    assert fake_tax_container.items["trec_1"]["lastPortalDownloadAt"].endswith("Z")


def test_public_tax_receipts_download_api_downloads_blob_with_download_ticket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "test-download-ticket-secret")
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.download_blob_bytes",
        lambda *, blob_name, container_name: b"%PDF-1.4"
        if (container_name, blob_name) == ("tax-receipts", "evt_tax/trec_1.pdf")
        else b"",
    )
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )
    reset_portal_auth_env(monkeypatch)
    request = build_request(
        "http://localhost:7075/api/v1/tax-receipts/download",
        body=json.dumps(
            {
                "downloadTicket": ticket,
                "eventId": "evt_tax",
                "receiptIds": ["trec_1"],
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Host": "localhost:7075",
            "Origin": "http://localhost:7075",
        },
        method="POST",
    )

    response = public_tax_receipts_download_api(request)

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="receipt-12345678-1.pdf"'
    )
    assert response.get_body() == b"%PDF-1.4"
    assert fake_tax_container.items["trec_1"]["downloadCount"] == 1
    assert fake_tax_container.items["trec_1"]["lastDownloadAt"].endswith("Z")
    assert fake_tax_container.items["trec_1"].get("portalDownloadCount", 0) == 0


def test_public_tax_receipts_download_api_blocks_repeated_public_receipt_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "test-download-ticket-secret")
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "downloadCount": 1,
        "lastDownloadAt": "2999-05-01T00:00:00Z",
        "lastDownloadSubjectKey": "lookup_subject",
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1"],
        subject_key="lookup_subject",
    )
    reset_portal_auth_env(monkeypatch)

    response = public_tax_receipts_download_api(
        build_request(
            "http://localhost:7075/api/v1/tax-receipts/download",
            body=json.dumps(
                {
                    "downloadTicket": ticket,
                    "eventId": "evt_tax",
                    "receiptIds": ["trec_1"],
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Host": "localhost:7075",
                "Origin": "http://localhost:7075",
            },
            method="POST",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 429
    assert "tax_receipt_download_cooldown" in body
    assert "trec_1" in body
    assert fake_tax_container.items["trec_1"]["downloadCount"] == 1


def test_public_tax_receipts_download_api_downloads_full_selection_when_some_are_not_cooling_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "test-download-ticket-secret")
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "downloadCount": 1,
        "lastDownloadAt": "2999-05-01T00:00:00Z",
        "lastDownloadSubjectKey": "lookup_subject",
    }
    fake_tax_container.items["trec_2"] = {
        "id": "trec_2",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_2.pdf",
        "fileName": "receipt-12345678-2.pdf",
        "fileSequence": 2,
        "contentType": "application/pdf",
        "downloadCount": 0,
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.download_blob_bytes",
        lambda *, blob_name, container_name: {
            ("tax-receipts", "evt_tax/trec_1.pdf"): b"%PDF-1",
            ("tax-receipts", "evt_tax/trec_2.pdf"): b"%PDF-2",
        }[(container_name, blob_name)],
    )
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1", "trec_2"],
        subject_key="lookup_subject",
    )
    reset_portal_auth_env(monkeypatch)

    response = public_tax_receipts_download_api(
        build_request(
            "http://localhost:7075/api/v1/tax-receipts/download",
            body=json.dumps(
                {
                    "downloadTicket": ticket,
                    "eventId": "evt_tax",
                    "receiptIds": ["trec_1", "trec_2"],
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Host": "localhost:7075",
                "Origin": "http://localhost:7075",
            },
            method="POST",
        )
    )

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="tax-receipts.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(response.get_body())) as zip_file:
        assert sorted(zip_file.namelist()) == [
            "receipt-12345678-1.pdf",
            "receipt-12345678-2.pdf",
        ]
        assert zip_file.read("receipt-12345678-1.pdf") == b"%PDF-1"
        assert zip_file.read("receipt-12345678-2.pdf") == b"%PDF-2"
    assert fake_tax_container.items["trec_1"]["downloadCount"] == 2
    assert fake_tax_container.items["trec_2"]["downloadCount"] == 1
    assert fake_tax_container.items["trec_1"]["lastDownloadSubjectKey"] == "lookup_subject"
    assert fake_tax_container.items["trec_2"]["lastDownloadSubjectKey"] == "lookup_subject"


def test_tax_receipt_download_ticket_allows_subset_of_receipts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TAX_RECEIPT_DOWNLOAD_TICKET_SECRET", "test-download-ticket-secret")
    ticket = build_tax_receipt_download_ticket(
        event_id="evt_tax",
        receipt_ids=["trec_1", "trec_2"],
    )

    assert is_valid_tax_receipt_download_ticket(
        ticket=ticket,
        event_id="evt_tax",
        receipt_ids=["trec_1"],
    )
    assert not is_valid_tax_receipt_download_ticket(
        ticket=ticket,
        event_id="evt_tax",
        receipt_ids=["trec_3"],
    )


def test_public_tax_receipts_download_api_downloads_multiple_blobs_as_zip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
    }
    fake_tax_container.items["trec_2"] = {
        "id": "trec_2",
        "eventId": "evt_tax",
        "sourceBlobName": "evt_tax/trec_2.png",
        "fileName": "receipt-87654321-1.png",
        "fileSequence": 1,
        "contentType": "image/png",
    }
    blob_payloads = {
        ("tax-receipts", "evt_tax/trec_1.pdf"): b"%PDF-1.4",
        ("tax-receipts", "evt_tax/trec_2.png"): b"PNG",
    }
    monkeypatch.setattr("src.functions.portal.get_tax_receipts_container", lambda: fake_tax_container)
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_blob_container_name",
        lambda: "tax-receipts",
    )
    monkeypatch.setattr(
        "src.functions.portal.download_blob_bytes",
        lambda *, blob_name, container_name: blob_payloads[(container_name, blob_name)],
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {"eventId": "evt_tax", "receiptIds": ["trec_1", "trec_2"]}
        ).encode("utf-8"),
        method="POST",
        url="http://localhost:7075/api/v1/tax-receipts/download",
    )

    response = public_tax_receipts_download_api(request)

    assert response.status_code == 200
    assert response.mimetype == "application/zip"
    assert response.headers["Content-Disposition"] == (
        'attachment; filename="tax-receipts.zip"'
    )
    with zipfile.ZipFile(io.BytesIO(response.get_body())) as zip_file:
        assert sorted(zip_file.namelist()) == [
            "receipt-12345678-1.pdf",
            "receipt-87654321-1.png",
        ]
        assert zip_file.read("receipt-12345678-1.pdf") == b"%PDF-1.4"
        assert zip_file.read("receipt-87654321-1.png") == b"PNG"
    assert fake_tax_container.items["trec_1"].get("downloadCount", 0) == 0
    assert fake_tax_container.items["trec_2"].get("downloadCount", 0) == 0
    assert fake_tax_container.items["trec_1"]["portalDownloadCount"] == 1
    assert fake_tax_container.items["trec_2"]["portalDownloadCount"] == 1


def test_portal_admin_completion_cert_change_requests_list_api_returns_pending_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_1"] = {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "舊公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_requests_container = FakeCompletionCertRequestsContainer()
    fake_requests_container.items["ccreq_1"] = {
        "id": "ccreq_1",
        "completionCertId": "ccert_1",
        "eventId": "evt_1",
        "status": "pending",
        "requesterEmail": "ming@example.com",
        "requesterNote": "公司名需要調整",
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": "2026-04-30T08:00:00Z",
        "updatedAt": "2026-04-30T08:00:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_cert_requests_container",
        lambda: fake_requests_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        method="GET",
        url="http://localhost:7075/api/v1/admin/completion-cert-change-requests",
        params={"status": "pending"},
    )

    response = portal_admin_completion_cert_change_requests_list_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"changeRequests"' in body
    assert '"id":"ccreq_1"' in body
    assert '"requesterNote":"公司名需要調整"' in body
    assert '"completionCert"' in body
    assert '"number":1' in body
    assert '"certStatus":"changeRequested"' in body


def test_portal_admin_completion_cert_change_requests_review_api_approves_and_updates_cert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_1"] = {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "舊公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_requests_container = FakeCompletionCertRequestsContainer()
    fake_requests_container.items["ccreq_1"] = {
        "id": "ccreq_1",
        "completionCertId": "ccert_1",
        "eventId": "evt_1",
        "status": "pending",
        "requesterEmail": "ming@example.com",
        "requesterNote": "公司名需要調整",
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": "2026-04-30T08:00:00Z",
        "updatedAt": "2026-04-30T08:00:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_cert_requests_container",
        lambda: fake_requests_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "status": "approved",
                "email": "new@example.com",
                "name": "王小明",
                "organization": "新公司",
                "reviewNote": "已修正",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"requestid": "ccreq_1"},
        url="http://localhost:7075/api/v1/admin/completion-cert-change-requests/ccreq_1",
    )

    response = portal_admin_completion_cert_change_requests_review_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"status":"approved"' in body
    assert fake_completion_container.items["ccert_1"]["email"] == "new@example.com"
    assert fake_completion_container.items["ccert_1"]["organization"] == "新公司"
    assert fake_completion_container.items["ccert_1"]["certStatus"] == "notIssued"
    assert fake_requests_container.items["ccreq_1"]["status"] == "approved"
    assert fake_requests_container.items["ccreq_1"]["reviewedBy"] == "admin@iplayground.io"
    assert fake_requests_container.items["ccreq_1"]["reviewedAt"].endswith("Z")
    assert fake_requests_container.items["ccreq_1"]["reviewNote"] == "已修正"


def test_portal_admin_completion_cert_change_requests_review_api_rejects_pending_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_1"] = {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "舊公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_requests_container = FakeCompletionCertRequestsContainer()
    fake_requests_container.items["ccreq_1"] = {
        "id": "ccreq_1",
        "completionCertId": "ccert_1",
        "eventId": "evt_1",
        "status": "pending",
        "requesterEmail": "ming@example.com",
        "requesterNote": "公司名需要調整",
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": "2026-04-30T08:00:00Z",
        "updatedAt": "2026-04-30T08:00:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_cert_requests_container",
        lambda: fake_requests_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "status": "rejected",
                "email": "changed@example.com",
                "name": "變更姓名",
                "organization": "變更公司",
                "reviewNote": "資料不符",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"requestid": "ccreq_1"},
        url="http://localhost:7075/api/v1/admin/completion-cert-change-requests/ccreq_1",
    )

    response = portal_admin_completion_cert_change_requests_review_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"status":"rejected"' in body
    assert fake_completion_container.items["ccert_1"]["email"] == "ming@example.com"
    assert fake_completion_container.items["ccert_1"]["name"] == "王小明"
    assert fake_completion_container.items["ccert_1"]["organization"] == "舊公司"
    assert fake_completion_container.items["ccert_1"]["certStatus"] == "notIssued"
    assert fake_requests_container.items["ccreq_1"]["status"] == "rejected"
    assert fake_requests_container.items["ccreq_1"]["reviewedBy"] == "admin@iplayground.io"
    assert fake_requests_container.items["ccreq_1"]["reviewedAt"].endswith("Z")
    assert fake_requests_container.items["ccreq_1"]["reviewNote"] == "資料不符"


def test_portal_admin_completion_cert_change_requests_review_api_rejects_once_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_1"] = {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "舊公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_requests_container = FakeCompletionCertRequestsContainer()
    fake_requests_container.items["ccreq_1"] = {
        "id": "ccreq_1",
        "completionCertId": "ccert_1",
        "eventId": "evt_1",
        "status": "approved",
        "requesterEmail": "ming@example.com",
        "requesterNote": "公司名需要調整",
        "reviewedBy": "admin@iplayground.io",
        "reviewedAt": "2026-04-30T08:30:00Z",
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": "2026-04-30T08:00:00Z",
        "updatedAt": "2026-04-30T08:30:00Z",
    }
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_cert_requests_container",
        lambda: fake_requests_container,
    )
    request = build_authorized_portal_api_request(
        monkeypatch,
        body=json.dumps(
            {
                "eventId": "evt_1",
                "status": "rejected",
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        method="PUT",
        route_params={"requestid": "ccreq_1"},
        url="http://localhost:7075/api/v1/admin/completion-cert-change-requests/ccreq_1",
    )

    response = portal_admin_completion_cert_change_requests_review_api(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 409
    assert "此修改申請已完成審核" in body
    assert fake_requests_container.items["ccreq_1"]["status"] == "approved"


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
    assert body.index('data-view-target="completion-certs"') < body.index(
        'data-view-target="completion-reviews"'
    )
    assert body.index('data-view-target="completion-reviews"') < body.index(
        'data-view-target="tax-receipts"'
    )
    assert 'data-view-target="completion-certs"' in body
    assert 'data-view-target="tax-receipts"' in body
    assert 'data-view-target="completion-reviews"' in body
    assert 'data-view-target="events"' in body
    assert 'data-view-path="/portal/dashboard/welcome"' in body
    assert 'data-view-path="/portal/dashboard/completion-certs"' in body
    assert 'data-view-path="/portal/dashboard/tax-receipts"' in body
    assert 'data-view-path="/portal/dashboard/completion-reviews"' in body
    assert 'data-view-path="/portal/dashboard/events"' in body
    assert "檢視清單" not in body
    assert "上傳清單" not in body
    assert "活動管理" in body
    assert "活動與文件設定" in body
    assert "清單與資料上傳" in body
    assert "PDF/圖檔上傳與管理" in body
    assert "修改審核" in body
    assert "完訓證明申請處理" in body
    assert "單筆文件上傳" not in body
    assert "管理活動與可申請文件" not in body
    assert "清單檢視與上傳完訓證明資料" not in body
    assert "清單檢視與上傳 407 收據聯" not in body
    assert 'id="portal-event-create-dialog"' in body
    assert 'id="portal-completion-upload-dialog"' in body
    assert 'id="portal-tax-upload-dialog"' in body
    assert 'class="event-dialog-backdrop portal-event-dialog-backdrop"' in body
    assert 'id="portal-event-name-input"' in body
    assert 'id="portal-event-form-submit" type="button" disabled' in body
    assert 'id="portal-event-status-text">下架</strong>' in body
    assert 'id="portal-event-status-checkbox"' in body
    assert 'id="portal-event-status-checkbox"\n              name="eventStatus"' in body
    assert "完訓證明開放下載時間" in body
    assert 'id="portal-event-completion-download-setting"' in body
    assert "data-completion-document-type-option" in body
    assert 'class="form-checkbox-option document-type-option document-type-option-with-setting"' in body
    assert 'class="document-type-checkbox-control"' in body
    assert 'id="portal-event-completion-download-starts-at-label"' in body
    assert 'class="field-label document-type-setting-toggle"' in body
    assert "data-completion-download-toggle" in body
    assert 'role="button"' in body
    assert 'tabindex="0"' in body
    assert 'aria-labelledby="portal-event-completion-download-starts-at-label"' in body
    assert 'for="portal-event-completion-download-starts-at"' not in body
    assert 'id="portal-event-completion-download-starts-at"' in body
    assert 'name="completionCertDownloadStartsAt"' in body
    assert 'id="portal-event-start-date"' in body
    assert 'name="eventStartDate"' in body
    assert 'id="portal-event-end-date"' in body
    assert 'name="eventEndDate"' in body
    assert 'class="field event-date-field"' in body
    assert 'class="document-type-setting-row"' in body
    assert 'id="portal-event-completion-hours"' in body
    assert 'name="completionHours"' in body
    assert "完訓總時數" in body
    assert 'class="form-datetime-input document-type-hours-input"' in body
    assert 'type="number"' not in body
    assert 'class="form-datetime-input document-type-datetime-input"' in body
    assert 'type="datetime-local"' not in body
    assert 'type="text"' in body
    assert 'inputmode="numeric"' in body
    assert 'placeholder="---- / -- / -- --:--"' in body
    assert "2[0-3]" in body
    assert "截止" not in body
    assert body.count('autocomplete="off"') == 8
    assert body.count('data-1p-ignore="true"') == 4
    assert body.count('data-op-ignore="true"') == 4
    assert body.count('data-lpignore="true"') == 4
    assert body.count('data-bwignore="true"') == 4
    assert body.count('data-protonpass-ignore="true"') == 4
    assert body.count('data-form-type="other"') == 4
    assert "data-portal-csrf-token" in body
    assert 'id="portal-completion-upload-file"' in body
    assert 'id="portal-completion-upload-file-name"' in body
    assert 'id="portal-completion-upload-submit"' in body
    assert 'id="portal-completion-upload-event"' in body
    assert 'id="portal-completion-upload-mapping"' in body
    assert 'id="portal-completion-upload-mapping-fields"' in body
    assert 'id="portal-completion-upload-event-select"' not in body
    assert 'id="portal-completion-upload-event-trigger"' not in body
    assert 'id="portal-completion-upload-event-options"' not in body
    assert 'id="portal-completion-upload-event-value"' in body
    assert 'class="field-static-value" id="portal-completion-upload-event-value"' in body
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
    assert 'id="portal-tax-upload-file"' in body
    assert 'id="portal-tax-upload-file-name"' in body
    assert 'id="portal-tax-upload-submit"' in body
    assert 'id="portal-tax-upload-event"' in body
    assert 'id="portal-tax-upload-event-select"' not in body
    assert 'id="portal-tax-upload-event-trigger"' not in body
    assert 'id="portal-tax-upload-event-options"' not in body
    assert 'id="portal-tax-upload-event-value"' in body
    assert 'class="field-static-value" id="portal-tax-upload-event-value"' in body
    assert 'id="portal-tax-upload-tax-id"' in body
    assert 'id="portal-tax-upload-amount"' in body
    assert 'id="portal-tax-upload-generated-at"' in body
    assert 'id="portal-tax-upload-errors"' in body
    assert 'placeholder="---- / -- / -- --:--:--"' in body
    assert "[0-5][0-9]:[0-5][0-9]" in body
    assert 'id="portal-tax-upload-continue"' in body
    assert 'id="portal-tax-upload-continue-option"' in body
    assert 'class="form-checkbox-option document-upload-continue-option"' in body
    assert 'class="event-status-switch-option document-upload-continue-option"' not in body
    assert 'id="portal-tax-upload-continue-label"' not in body
    assert 'id="portal-tax-upload-continue-text"' not in body
    assert body.index('id="portal-tax-upload-submit"') < body.index('id="portal-tax-upload-continue-option"')
    assert 'aria-labelledby="portal-tax-upload-event-label portal-tax-upload-event-value"' not in body
    assert 'accept=".pdf,application/pdf,image/png,image/jpeg,.png,.jpg,.jpeg"' in body
    assert "新增營業稅繳稅證明" in body
    assert "拖曳或選擇 PDF、PNG、JPG" in body
    assert "可將檔案拖曳到這裡" in body
    assert "尚未選擇 PDF 或圖檔" in body
    assert "每次新增一筆資料" in body
    assert "還有其他檔案要上傳" in body
    assert 'id="portal-tax-upload-cancel"' in body
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
    assert 'class="form-checkbox-option document-type-option"' in body
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
    assert 'src="/assets/portal-datetime-picker.js"' in body
    assert 'src="/assets/portal-event-cache.js"' in body
    assert 'src="/assets/portal-dashboard.js"' in body
    assert body.index('src="/assets/portal-datetime-picker.js"') < body.index(
        'src="/assets/portal-event-cache.js"'
    )
    assert body.index('src="/assets/portal-event-cache.js"') < body.index(
        'src="/assets/portal-dashboard.js"'
    )
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
    assert "Max-Age=28800" in session_cookie_header

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

    def fail_if_events_are_queried(**_: Any) -> list[dict[str, Any]]:
        raise AssertionError("welcome page should not query Cosmos DB before rendering HTML")

    monkeypatch.setattr("src.functions.portal.list_event_documents", fail_if_events_are_queried)

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
    assert 'class="metric-overview"' in body
    assert 'id="recent-activity-metrics-title"' in body
    assert 'class="metric-section metric-panel"' in body
    assert 'class="content-card metric-card"' not in body
    assert 'class="metric-card"' in body
    assert 'id="completion-metrics-title"' in body
    assert 'id="tax-receipt-metrics-title"' in body
    assert "完訓證明" in body
    assert "營業稅繳稅證明" in body
    assert "最近一期活動資料" in body
    assert body.count("最近一期活動資料") == 1
    assert "下列是最近一期活動的資料" not in body
    assert 'id="welcome-metric-source"' in body
    assert "資料來源：--" in body
    assert 'id="welcome-metric-overview"' in body
    assert 'aria-busy="true"' in body
    assert 'data-metric-field="completion.downloadableCount"' in body
    assert 'data-metric-field="completion.downloadCount"' in body
    assert 'data-metric-field="completion.verificationCount"' in body
    assert 'data-metric-field="completion.pendingCount"' in body
    assert 'data-metric-field="taxReceipt.receiptCount"' in body
    assert 'data-metric-field="taxReceipt.queriedCompanyCount"' in body
    assert 'data-metric-field="taxReceipt.downloadCount"' in body
    assert 'data-metric-field="taxReceipt.totalAmount"' in body
    assert "<strong class=\"metric-value is-loading\" data-metric-field=\"completion.downloadableCount\">--</strong>" in body
    assert "<strong class=\"metric-value is-loading\" data-metric-field=\"taxReceipt.totalAmount\">--</strong>" in body
    assert "載入中" not in body
    assert "系統可下載數" in body
    assert "下載人次" in body
    assert "驗證次數" in body
    assert "待處理案件數量" in body
    assert "收據張數" in body
    assert "已查詢公司數" in body
    assert "已建檔公司數" not in body
    assert "已下載次數" in body
    assert "收據總金額" in body
    assert "$186,000" not in body
    assert "NT$ 186K" not in body
    assert "上傳檔案數" not in body
    assert "尚未下載公司數" not in body
    assert "待確認筆數" not in body
    assert "目前已完成完訓證明檔案建立" in body
    assert "目前尚未完成發證或仍需管理者處理的完訓證明案件總數" in body
    assert "尚待匯入、發證或補件確認的完訓證明案件總數" not in body
    assert "最近一期活動已新增營業稅繳稅證明的金額合計" in body
    assert 'href="/assets/favicon.png"' in body
    assert 'src="/assets/portal-dashboard-welcome.js"' in body


def test_portal_admin_dashboard_welcome_metrics_api_returns_completion_metrics_from_cosmos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch, display_name="系統管理者")
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_1"] = {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "好玩公司",
        "email": "ming@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "issued",
        "issuedPdfBlobName": "issued/ccert_1.pdf",
        "verificationTokenHash": "hash-1",
        "issuedAt": "2026-04-28T06:02:00Z",
        "downloadCount": 2,
        "verificationCount": 5,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_completion_container.items["ccert_2"] = {
        "id": "ccert_2",
        "eventId": "evt_1",
        "number": 2,
        "kktixId": "KKTIX-002",
        "badgeName": "Hua",
        "ticketName": "一般票",
        "name": "王小華",
        "organization": "好玩公司",
        "email": "hua@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "issued",
        "issuedPdfBlobName": "issued/ccert_2.pdf",
        "verificationTokenHash": "hash-2",
        "issuedAt": "2026-04-28T06:03:00Z",
        "lastDownloadAt": "2026-04-29T06:03:00Z",
        "verificationCount": 7,
        "createdAt": "2026-04-28T06:03:00Z",
    }
    fake_completion_container.items["ccert_3"] = {
        "id": "ccert_3",
        "eventId": "evt_1",
        "number": 3,
        "kktixId": "KKTIX-003",
        "badgeName": "Lin",
        "ticketName": "一般票",
        "name": "林小安",
        "organization": "好玩公司",
        "email": "lin@example.com",
        "attendanceStatus": "notCheckedIn",
        "certStatus": "changeRequested",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "issuedAt": None,
        "verificationCount": 3,
        "createdAt": "2026-04-28T06:04:00Z",
    }
    fake_tax_container = FakeTaxReceiptsContainer()
    fake_tax_container.items["trec_1"] = {
        "id": "trec_1",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 186000,
        "generatedAt": "2026-05-13T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_1.pdf",
        "fileName": "receipt-12345678-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 100,
        "downloadCount": 4,
        "portalDownloadCount": 99,
        "createdAt": "2026-05-13T15:00:44Z",
        "updatedAt": "2026-05-13T15:00:44Z",
    }
    fake_tax_container.items["trec_2"] = {
        "id": "trec_2",
        "eventId": "evt_tax",
        "taxId": "12345678",
        "amount": 2000,
        "generatedAt": "2026-05-14T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_2.pdf",
        "fileName": "receipt-12345678-2.pdf",
        "fileSequence": 2,
        "contentType": "application/pdf",
        "fileSize": 100,
        "downloadCount": 1,
        "portalDownloadCount": 88,
        "createdAt": "2026-05-14T15:00:44Z",
        "updatedAt": "2026-05-14T15:00:44Z",
    }
    fake_tax_container.items["trec_3"] = {
        "id": "trec_3",
        "eventId": "evt_tax",
        "taxId": "87654321",
        "amount": 3000,
        "generatedAt": "2026-05-15T15:00:44Z",
        "sourceBlobName": "evt_tax/trec_3.pdf",
        "fileName": "receipt-87654321-1.pdf",
        "fileSequence": 1,
        "contentType": "application/pdf",
        "fileSize": 100,
        "downloadCount": 2,
        "portalDownloadCount": 77,
        "createdAt": "2026-05-15T15:00:44Z",
        "updatedAt": "2026-05-15T15:00:44Z",
    }
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    monkeypatch.setattr(
        "src.functions.portal.list_event_documents",
        lambda **_: [
            {
                "id": "evt_1",
                "name": "iPlayground 2026",
                "status": "open",
                "documentTypes": ["completionCert"],
                "eventStartDate": "2026-05-03",
                "eventEndDate": "2026-05-04",
                "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
            },
            {
                "id": "evt_tax",
                "name": "營業稅活動",
                "status": "open",
                "documentTypes": ["taxReceipt"],
                "eventStartDate": "2026-04-01",
                "eventEndDate": "2026-04-02",
                "completionCertDownloadStartsAt": None,
            },
        ],
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )
    monkeypatch.setattr(
        "src.functions.portal.get_tax_receipts_container",
        lambda: fake_tax_container,
    )

    response = portal_admin_dashboard_welcome_metrics_api(
        build_authorized_portal_api_request(
            monkeypatch,
            method="GET",
            url="http://localhost:7075/api/v1/admin/dashboard/welcome-metrics",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert '"completionCertMetrics"' in body
    assert '"eventName":"iPlayground 2026"' in body
    assert '"downloadableCount":2' in body
    assert '"downloadCount":3' in body
    assert '"verificationCount":15' in body
    assert '"pendingCount":1' in body
    assert '"taxReceiptMetrics"' in body
    assert '"eventName":"營業稅活動"' in body
    assert '"receiptCount":3' in body
    assert '"queriedCompanyCount":null' in body
    assert '"downloadCount":7' in body
    assert '"downloadCount":264' not in body
    assert '"totalAmount":191000' in body
    assert '"downloadableCount":128' not in body
    assert '"downloadCount":18' not in body
    assert '"verificationCount":46' not in body


def test_portal_admin_dashboard_welcome_metrics_api_uses_latest_open_event_start_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch, display_name="系統管理者")
    fake_completion_container = FakeCompletionCertsContainer()
    fake_completion_container.items["ccert_old"] = {
        "id": "ccert_old",
        "eventId": "evt_old",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Old",
        "ticketName": "一般票",
        "name": "舊活動會員",
        "organization": "好玩公司",
        "email": "old@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "issued",
        "issuedPdfBlobName": "issued/ccert_old.pdf",
        "verificationTokenHash": "hash-old",
        "issuedAt": "2026-04-28T06:02:00Z",
        "downloadCount": 1,
        "verificationCount": 99,
        "createdAt": "2026-04-28T06:02:00Z",
    }
    fake_completion_container.items["ccert_latest"] = {
        "id": "ccert_latest",
        "eventId": "evt_latest_open",
        "number": 1,
        "kktixId": "KKTIX-002",
        "badgeName": "Latest",
        "ticketName": "一般票",
        "name": "最新活動會員",
        "organization": "好玩公司",
        "email": "latest@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "issued",
        "issuedPdfBlobName": "issued/ccert_latest.pdf",
        "verificationTokenHash": "hash-latest",
        "issuedAt": "2026-05-28T06:02:00Z",
        "downloadCount": 1,
        "verificationCount": 7,
        "createdAt": "2026-05-28T06:02:00Z",
    }
    fake_completion_container.items["ccert_unlisted"] = {
        "id": "ccert_unlisted",
        "eventId": "evt_newer_unlisted",
        "number": 1,
        "kktixId": "KKTIX-003",
        "badgeName": "Hidden",
        "ticketName": "一般票",
        "name": "下架活動會員",
        "organization": "好玩公司",
        "email": "hidden@example.com",
        "attendanceStatus": "checkedIn",
        "certStatus": "issued",
        "issuedPdfBlobName": "issued/ccert_unlisted.pdf",
        "verificationTokenHash": "hash-hidden",
        "issuedAt": "2026-06-28T06:02:00Z",
        "downloadCount": 1,
        "verificationCount": 42,
        "createdAt": "2026-06-28T06:02:00Z",
    }
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    monkeypatch.setattr(
        "src.functions.portal.list_event_documents",
        lambda **_: [
            {
                "id": "evt_old",
                "name": "較早上架活動",
                "status": "open",
                "documentTypes": ["completionCert"],
                "eventStartDate": "2026-05-01",
                "eventEndDate": "2026-05-02",
            },
            {
                "id": "evt_newer_unlisted",
                "name": "最新下架活動",
                "status": "unlisted",
                "documentTypes": ["completionCert"],
                "eventStartDate": "2026-07-01",
                "eventEndDate": "2026-07-02",
            },
            {
                "id": "evt_latest_open",
                "name": "最新上架活動",
                "status": "open",
                "documentTypes": ["completionCert"],
                "eventStartDate": "2026-06-01",
                "eventEndDate": "2026-06-02",
            },
        ],
    )
    monkeypatch.setattr(
        "src.functions.portal.get_completion_records_container",
        lambda: fake_completion_container,
    )

    response = portal_admin_dashboard_welcome_metrics_api(
        build_authorized_portal_api_request(
            monkeypatch,
            method="GET",
            url="http://localhost:7075/api/v1/admin/dashboard/welcome-metrics",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"eventName":"最新上架活動"' in body
    assert '"verificationCount":7' in body
    assert '"verificationCount":99' not in body
    assert '"verificationCount":42' not in body


def test_portal_admin_dashboard_welcome_metrics_api_prefers_preaggregated_completion_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch, display_name="系統管理者")
    monkeypatch.setattr("src.functions.portal.get_events_container", FakeEventsContainer)
    monkeypatch.setattr(
        "src.functions.portal.list_event_documents",
        lambda **_: [
            {
                "id": "evt_1",
                "name": "iPlayground 2026",
                "status": "open",
                "documentTypes": ["completionCert"],
                "eventStartDate": "2026-05-03",
                "eventEndDate": "2026-05-04",
                "metrics": {
                    "completionCert": {
                        "downloadableCount": 12,
                        "downloadCount": 1,
                        "verificationCount": 5,
                        "pendingCount": 2,
                    }
                },
            }
        ],
    )

    def fail_if_completion_documents_are_queried(**_: Any) -> list[dict[str, Any]]:
        raise AssertionError("welcome metrics should use preaggregated event metrics")

    monkeypatch.setattr(
        "src.functions.portal.list_completion_cert_documents",
        fail_if_completion_documents_are_queried,
    )

    response = portal_admin_dashboard_welcome_metrics_api(
        build_authorized_portal_api_request(
            monkeypatch,
            method="GET",
            url="http://localhost:7075/api/v1/admin/dashboard/welcome-metrics",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert '"downloadableCount":12' in body
    assert '"downloadCount":1' in body
    assert '"verificationCount":5' in body
    assert '"pendingCount":2' in body


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
    assert "不可下載" not in body
    assert "可下載" not in body
    assert "報名序號" in body
    assert 'class="document-list-table completion-cert-table"' in body
    assert 'class="completion-cert-col-number"' in body
    assert 'class="completion-cert-col-organization"' in body
    assert 'class="completion-cert-col-ticket"' in body
    assert 'class="completion-cert-col-actions"' in body
    assert '<th scope="col">ID</th>' in body
    assert '<th scope="col">Badge Name</th>' in body
    assert body.index("<th scope=\"col\">姓名</th>") < body.index("<th scope=\"col\">公司名</th>")
    assert "票種" in body
    assert body.index("<th scope=\"col\">公司名</th>") < body.index("<th scope=\"col\">Email</th>")
    assert body.index("<th scope=\"col\">Email</th>") < body.index("<th scope=\"col\">票種</th>")
    assert body.index('data-field="organization"') < body.index('data-field="email"')
    assert body.index('data-field="email"') < body.index('data-field="ticketName"')
    assert "操作" in body
    assert "下載" in body
    assert "修改" in body
    assert 'id="completion-cert-row-template"' in body
    assert 'id="completion-cert-table-body"' in body
    assert 'id="completion-cert-empty-row"' in body
    assert 'id="completion-pagination"' in body
    assert 'aria-label="完訓證明清單分頁"' in body
    assert 'id="completion-page-prev"' in body
    assert 'id="completion-page-status"' in body
    assert 'id="completion-page-next"' in body
    assert "第 1 / 1 頁" in body
    assert 'class="document-row-actions"' in body
    assert 'class="secondary-button document-download-button"' in body
    assert 'class="secondary-button document-edit-button"' in body
    assert 'class="document-row-checkbox"' not in body
    assert 'class="event-status-switch-option document-row-status-switch"' in body
    assert 'class="event-status-switch-input document-download-switch-input"' in body
    assert 'data-action="toggle-downloadable"' in body
    assert 'data-field="downloadStatus"' not in body
    assert 'data-field="downloadState"' not in body
    assert 'aria-label="切換簽到狀態"' in body
    assert 'data-field="kktixId"' in body
    assert 'data-field="badgeName"' in body
    assert 'data-field="organization"' in body
    assert 'data-field="ticketName"' in body
    assert 'colspan="9"' in body
    assert "上傳完訓證明資料" in body
    assert 'id="completion-edit-dialog"' in body
    assert "修改完訓證明資料" in body
    assert "儲存修改" in body
    assert 'class="completion-edit-identity-row"' in body
    assert 'class="field completion-edit-number-field"' in body
    assert '<div class="field-static-value" id="completion-edit-badge-name">-</div>' in body
    assert '<div class="field-static-value" id="completion-edit-ticket-name">-</div>' in body
    assert 'id="completion-edit-name" name="completionEditName"' in body
    assert 'id="completion-edit-email" name="completionEditEmail"' in body
    assert 'data-1p-ignore data-lpignore="true" data-form-type="other"' in body
    assert 'id="completion-edit-email" name="email"' not in body
    assert 'id="completion-edit-badge-name" name="badgeName"' not in body
    assert 'id="completion-edit-ticket-name" name="ticketName"' not in body
    assert 'class="document-filter-form"' in body
    assert 'aria-label="完訓證明資料篩選"' in body
    assert '<th scope="col">活動</th>' not in body
    assert 'data-field="eventName"' not in body
    assert 'class="custom-select"' not in body
    assert 'class="custom-select-trigger"' not in body
    assert 'class="custom-select-menu"' not in body
    assert 'class="custom-select-option is-selected"' not in body
    assert 'role="listbox"' not in body
    assert 'role="option"' not in body
    assert 'id="completion-event-filter"' in body
    assert 'type="hidden"' in body
    assert 'name="eventName"' in body
    assert 'aria-required="true"' not in body
    assert "<select" not in body
    assert "iPlayground 2026" not in body
    assert "必填" not in body
    assert "套用篩選" not in body
    assert "completion-upload-file" in body
    assert 'id="completion-upload-file-name"' in body
    assert 'id="completion-upload-submit"' in body
    assert 'id="completion-upload-event"' in body
    assert 'id="completion-upload-mapping"' in body
    assert 'id="completion-upload-mapping-fields"' in body
    assert "配對 CSV 欄位" in body
    assert 'id="completion-upload-event-select"' not in body
    assert 'id="completion-upload-event-trigger"' not in body
    assert 'id="completion-upload-event-options"' not in body
    assert 'id="completion-upload-event-value"' in body
    assert 'class="field-static-value" id="completion-upload-event-value"' in body
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
    assert 'src="/assets/portal-event-cache.js"' in body
    assert 'src="/assets/page-alert.js"' in body
    assert 'src="/assets/portal-dashboard-completion-certs.js"' in body
    assert body.index('src="/assets/portal-event-cache.js"') < body.index(
        'src="/assets/page-alert.js"'
    )
    assert body.index('src="/assets/page-alert.js"') < body.index(
        'src="/assets/portal-dashboard-completion-certs.js"'
    )
    assert "document-workspace-grid" not in body
    assert "上傳資料" not in body
    assert '<p class="panel-kicker">完訓證明</p>' not in body
    assert "清單檢視" not in body
    assert "完訓證明資料載入中..." in body
    assert "目前活動尚無完訓證明資料。請先上傳完訓證明 CSV。" not in body
    assert "尚未串接完訓證明資料來源" not in body
    assert "尚無活動資料" in body
    assert "獨立工作頁" not in body


def test_portal_dashboard_completion_reviews_page_returns_html_when_user_is_authorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reset_portal_auth_env(monkeypatch)
    configure_portal_auth_bypass_env(monkeypatch)

    response = portal_dashboard_completion_reviews_page(
        build_request(
            "http://localhost:7075/portal/dashboard/completion-reviews",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "<title>修改審核 - 文件管理平台 - iPlayground</title>" in body
    assert 'class="portal-embedded-body"' in body
    assert "data-portal-csrf-token" in body
    assert "修改審核" in body
    assert "完訓證明修改申請清單" in body
    assert "修改申請載入中..." in body
    assert 'id="completion-review-refresh"' in body
    assert 'class="document-list-table completion-review-table"' in body
    assert 'id="completion-review-table-body"' in body
    assert 'id="completion-review-row-template"' in body
    assert '<th scope="col">申請時間</th>' in body
    assert '<th scope="col">報名序號</th>' in body
    assert '<th scope="col">目前姓名</th>' in body
    assert '<th scope="col">Email</th>' in body
    assert '<th scope="col">申請內容</th>' in body
    assert '<th scope="col">操作</th>' in body
    assert "審核修改申請" in body
    assert 'id="completion-review-dialog"' in body
    assert 'id="completion-review-requester-note"' in body
    assert 'id="completion-review-name"' in body
    assert 'id="completion-review-organization"' in body
    assert 'id="completion-review-email"' in body
    assert body.index('id="completion-review-email"') < body.index(
        'id="completion-review-requester-note"'
    )
    assert 'id="completion-review-email" name="completionReviewEmail" type="email" autocomplete="off" data-1p-ignore data-lpignore="true" data-form-type="other" readonly' in body
    assert 'id="completion-review-note"' in body
    assert 'class="form-textarea-shell completion-review-note-field"' in body
    assert 'class="form-textarea"' in body
    assert "駁回" in body
    assert "退回" not in body
    assert 'class="event-form-actions completion-review-form-actions"' in body
    assert body.index('id="completion-review-approve"') < body.index(
        'id="completion-review-cancel"'
    )
    assert body.index('id="completion-review-cancel"') < body.index(
        'id="completion-review-reject"'
    )
    assert 'class="brand-square-action completion-review-reject-button" id="completion-review-reject"' in body
    assert "通過並更新" in body
    assert 'src="/assets/page-alert.js"' in body
    assert 'src="/assets/portal-dashboard-completion-reviews.js"' in body


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
    assert "embedded-page-card" in body
    assert "document-workspace-card" in body
    assert "營業稅繳稅證明" in body
    assert "營業稅繳稅證明清單" in body
    assert "新增繳稅證明" in body
    assert "檢視已新增的營業稅繳稅證明" in body
    assert "PDF 或圖檔" in body
    assert 'class="document-filter-form tax-receipt-filter-form"' in body
    assert 'aria-label="營業稅繳稅證明篩選"' in body
    assert 'id="tax-event-filter"' in body
    assert 'id="tax-id-filter"' in body
    assert 'name="taxId"' in body
    assert 'type="search"' in body
    assert 'inputmode="numeric"' in body
    assert "搜尋統編" in body
    assert "輸入統編" in body
    assert 'id="tax-event-filter-select"' not in body
    assert 'id="tax-event-filter-trigger"' not in body
    assert 'id="tax-event-filter-options"' not in body
    assert 'id="tax-event-filter-value"' in body
    assert 'class="field-static-value" id="tax-event-filter-value"' in body
    assert "尚無活動資料" in body
    assert "套用至目前活動全部資料" not in body
    assert "設為可下載" not in body
    assert "設為停用" not in body
    assert 'id="tax-bulk-toolbar"' not in body
    assert 'id="tax-bulk-downloadable"' not in body
    assert 'id="tax-bulk-blocked"' not in body
    assert "統編" in body
    assert "金額" in body
    assert "產製時間" in body
    assert body.index('class="tax-receipt-col-generated-at" scope="col">產製時間</th>') < body.index(
        'class="tax-receipt-col-amount" scope="col">金額</th>'
    )
    assert body.index('data-field="generatedAt"') < body.index('data-field="amount"')
    assert "報名序號" not in body
    assert "姓名" not in body
    assert "Email" not in body
    assert 'class="document-list-table tax-receipt-table"' in body
    assert 'class="tax-receipt-col-actions"' in body
    assert "收據聯檔案" not in body
    assert "下載狀態" not in body
    assert "操作" in body
    assert "下載" in body
    assert "修改" in body
    assert "刪除" in body
    assert 'id="tax-receipt-row-template"' in body
    assert 'id="tax-receipt-table-body"' in body
    assert 'id="tax-receipt-empty-row"' in body
    assert 'id="tax-receipt-pagination"' in body
    assert 'id="tax-receipt-page-prev"' in body
    assert 'id="tax-receipt-page-status"' in body
    assert 'id="tax-receipt-page-next"' in body
    assert "營業稅繳稅證明清單分頁" in body
    assert 'class="document-row-actions"' in body
    assert 'class="secondary-button document-download-button"' in body
    assert 'class="document-file-icon"' in body
    assert 'class="secondary-button document-edit-button"' in body
    assert 'class="secondary-button document-delete-button"' in body
    assert 'class="event-status-switch-option document-row-status-switch"' not in body
    assert 'class="event-status-switch-input document-download-switch-input"' not in body
    assert 'data-action="toggle-downloadable"' not in body
    assert 'data-field="downloadStatus"' not in body
    assert 'aria-label="切換下載狀態"' not in body
    assert 'colspan="4"' in body
    assert "營業稅繳稅證明資料載入中..." in body
    assert 'id="tax-upload-open"' in body
    assert 'id="tax-upload-dialog"' in body
    assert 'aria-modal="true"' in body
    assert 'id="tax-upload-cancel"' in body
    assert 'id="tax-upload-file"' in body
    assert 'id="tax-upload-file-name"' in body
    assert 'id="tax-upload-submit"' in body
    assert 'id="tax-upload-event"' in body
    assert 'id="tax-upload-event-select"' not in body
    assert 'id="tax-upload-event-trigger"' not in body
    assert 'id="tax-upload-event-options"' not in body
    assert 'id="tax-upload-event-value"' in body
    assert 'class="field-static-value" id="tax-upload-event-value"' in body
    assert 'id="tax-upload-tax-id"' in body
    assert 'id="tax-upload-amount"' in body
    assert 'id="tax-upload-generated-at"' in body
    assert 'id="tax-upload-errors"' in body
    assert 'id="tax-upload-continue"' in body
    assert 'id="tax-upload-continue-option"' in body
    assert 'inputmode="decimal"' in body
    assert 'class="form-datetime-input"' in body
    assert 'type="datetime-local"' not in body
    assert 'placeholder="---- / -- / -- --:--:--"' in body
    assert "[0-5][0-9]:[0-5][0-9]" in body
    assert 'class="document-detail-grid"' in body
    assert 'class="document-upload-input"' in body
    assert 'class="document-upload-copy"' in body
    assert 'class="document-upload-file-name"' in body
    assert 'class="form-checkbox-option document-upload-continue-option"' in body
    assert 'class="event-status-switch-option document-upload-continue-option"' not in body
    assert 'id="tax-upload-continue-label"' not in body
    assert 'id="tax-upload-continue-text"' not in body
    assert body.index('id="tax-upload-submit"') < body.index('id="tax-upload-continue-option"')
    assert 'accept=".pdf,application/pdf,image/png,image/jpeg,.png,.jpg,.jpeg"' in body
    assert "拖曳或選擇 PDF、PNG、JPG" in body
    assert "每次新增一筆資料" in body
    assert "可將檔案拖曳到這裡" in body
    assert "還有其他檔案要上傳" in body
    assert "尚未選擇 PDF 或圖檔" in body
    assert 'src="/assets/portal-datetime-picker.js"' in body
    assert 'src="/assets/portal-event-cache.js"' in body
    assert 'src="/assets/page-alert.js"' in body
    assert 'src="/assets/portal-dashboard-tax-receipts.js"' in body
    assert body.index('src="/assets/portal-datetime-picker.js"') < body.index(
        'src="/assets/portal-event-cache.js"'
    )
    assert body.index('src="/assets/portal-event-cache.js"') < body.index(
        'src="/assets/page-alert.js"'
    )
    assert body.index('src="/assets/page-alert.js"') < body.index(
        'src="/assets/portal-dashboard-tax-receipts.js"'
    )
    assert "CSV" not in body
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
    assert "data-portal-csrf-token" in body
    assert "event-management-card" in body
    assert "event-management-panel" not in body
    assert "event-panel-heading" not in body
    assert 'id="event-list-title"' not in body
    assert "活動管理" in body
    assert "活動清單" in body
    assert 'class="event-list-col-name"' in body
    assert 'class="event-list-col-time"' not in body
    assert 'class="event-list-col-code"' not in body
    assert 'class="event-list-col-documents"' in body
    assert 'class="event-list-col-status"' in body
    assert 'id="event-list-body"' in body
    assert 'class="event-list-row"' not in body
    assert 'class="event-list-row" role="button"' not in body
    assert 'aria-label="編輯活動 iPlayground 2026"' not in body
    assert 'data-event-form-open="edit"' not in body
    assert 'data-event-name="iPlayground 2026"' not in body
    assert 'data-event-status="open"' not in body
    assert 'data-event-document-types="completionCert"' not in body
    assert "活動載入中" in body
    assert "活動時間" not in body
    assert "尚未建立活動" not in body
    assert "活動代碼" not in body
    assert "ipg-2026" not in body
    assert 'id="event-code-input"' not in body
    assert "申請期間" not in body
    assert "申請起始日" not in body
    assert "申請截止日" not in body
    assert 'id="event-create-open"' in body
    assert "建立活動" in body
    assert 'id="event-create-dialog"' in body
    assert body.count('autocomplete="off"') == 5
    assert body.count('data-1p-ignore="true"') == 1
    assert body.count('data-op-ignore="true"') == 1
    assert body.count('data-lpignore="true"') == 1
    assert body.count('data-bwignore="true"') == 1
    assert body.count('data-protonpass-ignore="true"') == 1
    assert body.count('data-form-type="other"') == 1
    assert 'aria-modal="true"' in body
    assert 'class="secondary-button event-cancel-button"' in body
    assert 'id="event-form-submit" type="button" disabled' in body
    assert 'id="event-create-close"' not in body
    assert "關閉建立活動畫面" not in body
    assert "活動狀態" in body
    assert 'id="event-start-date"' in body
    assert 'name="eventStartDate"' in body
    assert 'id="event-end-date"' in body
    assert 'name="eventEndDate"' in body
    assert 'class="field event-date-field"' in body
    assert 'class="document-type-setting-row"' in body
    assert 'id="event-completion-hours"' in body
    assert 'name="completionHours"' in body
    assert 'class="form-datetime-input document-type-hours-input"' in body
    assert 'type="number"' not in body
    assert "活動開始日期" in body
    assert "活動結束日期" in body
    assert "完訓總時數" in body
    assert 'id="event-status-text">下架</strong>' in body
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
    assert "完訓證明開放下載時間" in body
    assert 'id="event-completion-download-setting"' in body
    assert "data-completion-document-type-option" in body
    assert 'class="form-checkbox-option document-type-option document-type-option-with-setting"' in body
    assert 'class="document-type-checkbox-control"' in body
    assert 'id="event-completion-download-starts-at-label"' in body
    assert 'class="field-label document-type-setting-toggle"' in body
    assert "data-completion-download-toggle" in body
    assert 'role="button"' in body
    assert 'tabindex="0"' in body
    assert 'aria-labelledby="event-completion-download-starts-at-label"' in body
    assert 'for="event-completion-download-starts-at"' not in body
    assert 'id="event-completion-download-starts-at"' in body
    assert 'name="completionCertDownloadStartsAt"' in body
    assert 'src="/assets/portal-datetime-picker.js"' in body
    assert 'src="/assets/portal-event-cache.js"' in body
    assert 'src="/assets/portal-dashboard-events.js"' in body
    assert body.index('src="/assets/portal-datetime-picker.js"') < body.index(
        'src="/assets/portal-event-cache.js"'
    )
    assert body.index('src="/assets/portal-event-cache.js"') < body.index(
        'src="/assets/portal-dashboard-events.js"'
    )


def test_portal_css_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal.css",
            route_params={"asset_name": "portal.css"},
        )
    )
    body = response.get_body().decode("utf-8")
    theme_response = static_asset(
        build_request(
            "http://localhost:7075/assets/theme.css",
            route_params={"asset_name": "theme.css"},
        )
    )
    theme_body = theme_response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert theme_response.status_code == 200
    assert theme_response.mimetype == "text/css"
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
    assert ".metric-section" in body
    assert ".metric-panel" in body
    assert ".metric-section-heading" in body
    assert ".event-management-card" in body
    assert ".custom-select-trigger" in theme_body
    assert ".custom-select.is-single-option .custom-select-trigger" in theme_body
    assert ".custom-select-menu" in theme_body
    assert ".custom-select-option" in theme_body
    assert ".field-static-value" in theme_body
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
    assert ".document-download-switch-input" in body
    assert ".document-pagination" in body
    assert ".document-page-status" in body
    assert ".required-field-mark" not in body
    assert ".document-filter-submit" not in body
    assert ".document-list-table" in body
    assert ".tax-receipt-filter-form" in body
    assert "grid-template-columns: minmax(260px, 420px) minmax(180px, 240px);" in body
    assert ".completion-cert-table" in body
    assert ".completion-review-table" in body
    assert "table-layout: fixed;" in body
    assert ".completion-cert-col-badge {\n  width: 140px;" in body
    assert ".completion-review-col-note {\n  width: 330px;" in body
    assert ".completion-cert-col-name {\n  width: 140px;" in body
    assert ".completion-cert-col-email {\n  width: 250px;" in body
    assert ".completion-cert-col-organization,\n.completion-cert-col-ticket" in body
    assert ".completion-edit-identity-row" in body
    assert "grid-template-columns: minmax(72px, 0.56fr) minmax(104px, 0.8fr) minmax(160px, 1.4fr);" in body
    assert ".document-list-table th,\n.document-list-table td {\n  padding: 15px 16px;" in body
    assert ".document-list-table th,\n.document-list-table td {\n  padding: 15px 16px;\n  border-bottom: 1px solid rgba(81, 121, 254, 0.1);\n  text-align: left;\n  vertical-align: middle;\n  white-space: nowrap;" in body
    assert ".completion-cert-row [data-field=\"organization\"],\n.completion-cert-row [data-field=\"ticketName\"]" in body
    assert ".completion-cert-row [data-field=\"badgeName\"],\n.completion-cert-row [data-field=\"name\"],\n.completion-cert-row [data-field=\"organization\"],\n.completion-cert-row [data-field=\"email\"],\n.completion-cert-row [data-field=\"ticketName\"]" in body
    assert ".completion-review-row [data-field=\"requesterNote\"]" in body
    assert ".completion-review-note" in body
    assert ".completion-review-cancel-button" in body
    assert ".completion-review-reject-button" in body
    assert "border-radius: 18px;" in body
    assert "max-width: 10em;" in body
    assert "text-overflow: ellipsis;" in body
    assert ".document-download-button" in body
    assert ".document-download-button:disabled" in body
    assert ".document-page-button:disabled" in body
    assert ".document-row-actions" in body
    assert ".tax-receipt-row.is-disabled" in body
    assert ".tax-receipt-col-actions,\n.tax-receipt-table td:last-child" in body
    assert ".tax-receipt-table .document-row-actions" in body
    assert ".completion-cert-table.is-bulk-updating .completion-cert-row" in body
    assert ".event-status-switch-input:disabled + .event-status-switch-track" in body
    assert ".document-delete-button" in body
    assert ".document-upload-continue-option" in body
    assert ".form-checkbox-option.document-upload-continue-option" in body
    assert "-webkit-user-select: none;" in body
    assert ".document-upload-form" in body
    assert ".document-upload-dropzone" in body
    assert ".document-upload-dropzone.is-drag-active" in body
    assert ".document-upload-input" in body
    assert ".document-upload-copy" in body
    assert ".document-upload-file-name" in body
    assert ".document-detail-grid" in body
    assert ".document-file-icon" in body
    assert ".document-upload-form input[type=\"file\"]" not in body
    assert ".event-management-header" in body
    assert ".event-management-panel" not in body
    assert ".event-list-toolbar" not in body
    assert ".event-list-table" in body
    assert ".event-list-col-documents" in body
    assert ".event-list-col-time" not in body
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
    assert "border: 0;" in body
    assert "background: transparent;" in body
    assert ".event-status-switch-input:checked + .event-status-switch-track" in body
    assert ".event-status-switch-thumb" in body
    assert "transform: translateX(18px);" in body
    assert "select-caret" in theme_body
    assert ".event-status-badge.is-draft" not in body
    assert ".event-status-badge.is-unlisted" in body
    assert ".event-status-badge.is-open" in body
    assert ".document-type-pill-list" in body
    assert ".document-type-pill.is-completion-cert" in body
    assert ".document-type-pill.is-tax-receipt" in body
    assert ".document-type-pill.is-empty" in body
    assert ".form-checkbox-option" in theme_body
    assert ".document-type-option-with-setting" in body
    assert ".document-type-checkbox-control" in body
    assert ".document-type-setting" in body
    assert "grid-template-columns: 140px 70px;" in theme_body
    assert "grid-template-columns: 140px;" in theme_body
    assert "grid-template-columns: 130px 65px;" in theme_body
    assert "grid-template-columns: minmax(0, 1fr);" in body
    assert ".document-type-option-with-setting .document-type-setting" in body
    assert "margin-left: 34px;" in body
    assert ".document-type-option-with-setting {\n    grid-template-columns: 1fr;" not in body
    assert ".document-type-setting {\n    grid-template-columns: 1fr;" not in body
    assert ".document-type-setting[hidden]" in body
    assert ".document-type-setting-toggle" in body
    document_type_toggle_css = body[body.index(".document-type-setting-toggle") :]
    document_type_toggle_css = document_type_toggle_css[
        : document_type_toggle_css.index(".document-type-setting-toggle:focus-visible")
    ]
    assert "cursor: pointer;" not in document_type_toggle_css
    assert ".document-type-setting-toggle:focus-visible" in body
    assert ".form-datetime-input" in theme_body
    assert ".form-textarea" in theme_body
    assert ".form-textarea-shell" in theme_body
    assert ".form-textarea:focus" in theme_body
    assert ".form-textarea::placeholder" in theme_body
    assert ".form-datetime-input:focus" in theme_body
    assert ".form-datetime-picker-proxy" not in body
    assert ".form-datetime-picker" in theme_body
    assert ".form-datetime-picker-inline" in theme_body
    assert ".form-date-picker-inline" in theme_body
    assert ".form-datetime-picker-date" in theme_body
    assert ".form-datetime-picker-date-part" in theme_body
    assert ".form-datetime-picker-date-part.is-year" in theme_body
    assert ".form-datetime-picker-date-native" in theme_body
    assert ".form-datetime-picker-date-native::-webkit-calendar-picker-indicator" in theme_body
    assert ".form-datetime-picker-time" in theme_body
    assert ".form-datetime-picker-time-input" in theme_body
    assert ".form-datetime-picker-time-input:focus" in theme_body
    assert "grid-template-columns: calc(4ch + 2px) max-content calc(2ch + 2px) max-content calc(2ch + 2px) 22px;" in theme_body
    assert ".form-datetime-picker:has(.form-datetime-picker-time-input:nth-of-type(3))" in theme_body
    assert "grid-template-columns: 140px 98px;" in theme_body
    assert "grid-template-columns: minmax(26px, 30px) max-content minmax(26px, 30px);" in theme_body
    assert "grid-template-columns: calc(4.3ch + 2px) max-content calc(2.3ch + 2px) max-content calc(2.3ch + 2px) 22px;" in theme_body
    assert "grid-template-columns: minmax(24px, 26px) max-content minmax(24px, 26px);" in theme_body
    assert "transform: translateX(-18px);" in theme_body
    assert "gap: 0.2ch;" in theme_body
    assert ".form-datetime-input[hidden]" in theme_body
    assert "width: max-content;" in theme_body
    assert "padding: 8px 4px 8px 10px;" in theme_body
    assert ".document-type-datetime-input" in theme_body
    assert "min-height: 40px;" in theme_body
    assert "padding: 8px 12px;" in theme_body
    assert "background-image: none;" in theme_body
    assert ".event-cancel-button" in body
    assert "border-radius: 14px;" not in body
    assert "accent-color: var(--theme-accent-deep);" in theme_body
    assert "appearance: auto;" in theme_body
    assert "color-scheme: light;" in theme_body
    assert "accent-color: #ea6e1e;" in theme_body
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


def test_portal_event_cache_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-event-cache.js",
            route_params={"asset_name": "portal-event-cache.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'const adminEventsApiPath = "/api/v1/admin/events"' in body
    assert "sessionStorage" in body
    assert "ipg:portal:events:v1" in body
    assert "iPlaygroundPortalEvents" in body
    assert "getCachedEvents" in body
    assert "preload" in body
    assert "refresh" in body
    assert "upsertCachedEvent" in body
    assert "ipg:portal-events:updated" in body
    assert "iPlaygroundPortalAuth" in body
    assert "handleUnauthorizedResponse" in body
    assert "redirectToPortalEntry" in body
    assert 'const sessionStartedAtKey = "ipg:portal:session-started-at:v1"' in body
    assert "const sessionMaxAgeMs = 8 * 60 * 60 * 1000" in body
    assert "verifySession" in body


def test_portal_datetime_picker_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-datetime-picker.js",
            route_params={"asset_name": "portal-datetime-picker.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "window.iPlaygroundPortalDateTime" in body
    assert "const minDateTimeYear = 2018" in body
    assert "const maxDateTimeYear = 2099" in body
    assert "const taipeiUtcOffsetMinutes = 8 * 60" in body
    assert "formatCurrentDateTimeInputValue" in body
    assert "function formatDateInputValue" in body
    assert "function formatIsoDateInputValue" in body
    assert "now.getUTCHours()" in body
    assert "function formatDateTimeInputValue" in body
    assert "function formatUtcIsoDateTimeInputValue" in body
    assert "function formatDateTimeInputValueFromUtcIso" in body
    assert "function normalizeDateTimeInputValue" in body
    assert "function normalizeDateInputValue" in body
    assert "function parseUtcIsoDateTimeValue" in body
    assert "function parseIsoDateValue" in body
    assert "function parseDisplayDateParts" in body
    assert "formatUtcIsoDateTimeValue(utcDate)" in body
    assert "function getDaysInMonth" in body
    assert "function isValidDateTimeParts" in body
    assert "year >= minDateTimeYear" in body
    assert "year <= maxDateTimeYear" in body
    assert "parseDisplayDateTimeValue" in body
    assert "!isValidDateTimeParts(yearValue, monthValue, dayValue, hourValue, minuteValue, secondValue)" in body
    assert "function installDateTimePicker" in body
    assert "function installDateTimePicker(textInput, options = {})" in body
    assert "function installDatePicker(textInput)" in body
    assert "form-datetime-picker form-date-picker-inline" in body
    assert "const includeSeconds = options.includeSeconds === true" in body
    assert "textInput.type = \"datetime-local\"" not in body
    assert "textInput.showPicker()" not in body
    assert "textInput.hidden = true" in body
    assert "form-datetime-picker form-datetime-picker-inline" in body
    assert "document.createElement(\"select\")" not in body
    assert "document.createElement(\"input\")" in body
    assert "timeGroup.className = \"form-datetime-picker-time\"" in body
    assert "yearInput.maxLength = 4" in body
    assert "monthInput.maxLength = 2" in body
    assert "dayInput.maxLength = 2" in body
    assert "dateInput.type = \"date\"" in body
    assert "yearInput.setAttribute(\"aria-label\", \"年\")" in body
    assert "monthInput.setAttribute(\"aria-label\", \"月\")" in body
    assert "dayInput.setAttribute(\"aria-label\", \"日\")" in body
    assert "dateInput.setAttribute(\"aria-label\", \"日期選擇器\")" in body
    assert "document.createTextNode(\"/\")" in body
    assert "document.createTextNode(\":\")" in body
    assert "handleDateInput(yearInput, monthInput, 4)" in body
    assert "handleDateInput(monthInput, dayInput, 2)" in body
    assert "handleDateInput(dayInput, hourInput, 2)" in body
    assert "dateInput.addEventListener(\"input\", handleNativeDateInput)" in body
    assert "let isApplyingPickerValue = false" in body
    assert "let restoreDisplayValue = \"\"" in body
    assert "normalizeYearValue" in body
    assert "function getRestoreDisplayValue" in body
    assert "function isPickerValueComplete" in body
    assert "function isPickerValueValid" in body
    assert "function restorePreviousPickerValue" in body
    assert "if (!isPickerValueComplete() || !isPickerValueValid())" in body
    assert "if (!applyPickerValue())" in body
    assert "restorePreviousPickerValue();" in body
    assert "restoreDisplayValue = getRestoreDisplayValue();" in body
    assert "restoreDisplayValue = textInput.value;" in body
    assert "return false;" in body
    assert "normalizeTimeValue(hourInput.value)" in body
    assert "normalizeTimeValue(minuteInput.value)" in body
    assert "hourInput.value.length === 2" in body
    assert "minuteInput.value.length === 2" in body
    assert "if (isApplyingPickerValue)" in body
    assert "selectDateTimeInputValue" in body
    assert "installSelectAllOnFocus" in body
    assert "const pickerPartInputs = [yearInput, monthInput, dayInput, hourInput, minuteInput]" in body
    assert "const pickerControlInputs = [...pickerPartInputs, dateInput]" in body
    assert "function syncPickerDisabledState" in body
    assert "picker.classList.toggle(\"is-disabled\", isDisabled)" in body
    assert "input.disabled = isDisabled" in body
    assert "new MutationObserver(syncPickerDisabledState).observe(textInput" in body
    assert "function handlePickerPartNavigation" in body
    assert "event.key !== \"ArrowLeft\" && event.key !== \"ArrowRight\"" in body
    assert "const direction = event.key === \"ArrowLeft\" ? -1 : 1" in body
    assert "pickerPartInputs[currentIndex + direction]" in body
    assert "input.addEventListener(\"keydown\", handlePickerPartNavigation)" in body
    assert "function handlePickerReturn" in body
    assert "event.key !== \"Enter\" || event.isComposing || !isFinalTimeInput" in body
    assert "event.currentTarget.blur()" in body
    assert "datetime-picker-return" in body
    assert "input.addEventListener(\"keydown\", handlePickerReturn)" in body
    assert "hourInput.inputMode = \"numeric\"" in body
    assert "minuteInput.inputMode = \"numeric\"" in body
    assert "secondInput.inputMode = \"numeric\"" in body
    assert "hourInput.maxLength = 2" in body
    assert "minuteInput.maxLength = 2" in body
    assert "secondInput.maxLength = 2" in body
    assert "handleTimeInput(hourInput, minuteInput)" in body
    assert "handleTimeInput(minuteInput, includeSeconds ? secondInput : null)" in body
    assert "normalizeTimeValue" in body
    assert "normalizeAndApplyDateInput(yearInput)" in body
    assert "normalizeAndApplyTimeInput(hourInput)" in body
    assert "normalizeAndApplyTimeInput(minuteInput)" in body
    assert "normalizeAndApplyTimeInput(secondInput)" in body
    assert "hourInput.setAttribute(\"aria-label\", \"小時\")" in body
    assert "minuteInput.setAttribute(\"aria-label\", \"分鐘\")" in body
    assert "secondInput.setAttribute(\"aria-label\", \"秒\")" in body
    assert "timeGroup.append(document.createTextNode(\":\"), secondInput)" in body
    assert "textInput.getBoundingClientRect()" not in body
    assert "textInput.addEventListener(\"focus\", openPicker)" not in body
    assert "textInput.addEventListener(\"input\", syncInlinePicker)" in body


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
    assert "resolveCurrentFramePath" in body
    assert "handlePortalUnauthorizedResponse" in body
    assert "verifyPortalSession" in body
    assert "openDashboardEventDialog" in body
    assert "openDashboardCompletionUploadDialog" in body
    assert "portal-completion-upload-file-name" in body
    assert "portal-completion-upload-submit" in body
    assert "portal-completion-upload-event" in body
    assert "portal-completion-upload-mapping" in body
    assert "portal-completion-upload-mapping-fields" in body
    assert "portal-completion-upload-event-trigger" in body
    assert "updateDashboardCompletionUploadFileName" in body
    assert "isDashboardCompletionCsvFile" in body
    assert "getCompletionEventNameFromFrame" in body
    assert "applyDashboardCompletionUploadEventValue" in body
    assert "getDashboardCompletionUploadEventName" in body
    assert "loadDashboardCompletionUploadEvents" in body
    assert "renderDashboardCompletionUploadEventSelect" in body
    assert "fetch(adminEventsApiPath" in body
    assert "portal-completion-upload-event-options" in body
    assert "portal-completion-upload-event-select" in body
    assert "getFirstDashboardCompletionUploadEventValue" in body
    assert "isSingleOption" in body
    assert "openDashboardCompletionUploadEventSelect" in body
    assert "closeDashboardCompletionUploadEventSelect" in body
    assert "sendDashboardCompletionUploadFileToFrame" in body
    assert "handleDashboardCompletionUploadDrop" in body
    assert "assignDashboardCompletionUploadFile" in body
    assert "document.addEventListener(\"drop\", handleDashboardCompletionUploadDrop)" in body
    assert "new DataTransfer()" in body
    assert "completionUploadImportMessageType" in body
    assert "ipg:completion-upload:import" in body
    assert "adminCompletionCertsImportApiPath" in body
    assert "完訓證明資料匯入中..." in body
    assert "eventId: getDashboardCompletionUploadEventName()" in body
    assert "prepareDashboardCompletionUploadFieldMapping(selectedFile)" in body
    assert "file.text()" in body
    assert "readDashboardCompletionUploadFieldMapping" in body
    assert "fieldMapping: readDashboardCompletionUploadFieldMapping()" in body
    assert "\"X-Portal-CSRF-Token\": portalCsrfToken" in body
    assert "contentFrame.contentWindow?.postMessage" in body
    assert '.endsWith(".csv")' in body
    assert "openDashboardTaxUploadDialog" in body
    assert "portal-tax-upload-title" in body
    assert "portal-tax-upload-continue" in body
    assert "portal-tax-upload-file-name" in body
    assert "portal-tax-upload-submit" in body
    assert "portal-tax-upload-event" in body
    assert "portal-tax-upload-event-trigger" in body
    assert "portal-tax-upload-tax-id" in body
    assert "portal-tax-upload-amount" in body
    assert "portal-tax-upload-generated-at" in body
    assert "portal-tax-upload-errors" in body
    assert "updateDashboardTaxUploadFileName" in body
    assert "isDashboardTaxReceiptUploadFile" in body
    assert "validateDashboardTaxUploadForm" in body
    assert "invalidDashboardTaxUploadTaxIdMessage" in body
    assert "invalidDashboardTaxUploadAmountMessage" in body
    assert "請輸入大於 0 的整數金額。" in body
    assert "invalidDashboardTaxUploadGeneratedAtMessage" in body
    assert "/^(?:0|[1-9][0-9]*)$/.test(normalizedValue)" in body
    assert "getTaxEventNameFromFrame" in body
    assert "applyDashboardTaxUploadEventValue" in body
    assert "getDashboardTaxUploadEventName" in body
    assert "openDashboardTaxUploadEventSelect" in body
    assert "closeDashboardTaxUploadEventSelect" in body
    assert "sendDashboardTaxUploadFileToFrame" in body
    assert "handleDashboardTaxUploadDrop" in body
    assert "assignDashboardTaxUploadFile" in body
    assert "document.addEventListener(\"drop\", handleDashboardTaxUploadDrop)" in body
    assert "shouldContinueDashboardTaxUpload" in body
    assert "resetDashboardTaxUploadFieldsForNextFile" in body
    assert "setDashboardTaxUploadDialogMode" in body
    assert "dashboardTaxUploadTaxIdInput.readOnly = isEditMode" in body
    assert "統編不可修改；如需更正請刪除後重新新增。" in body
    assert "dashboardTaxUploadInitialDraftState" in body
    assert "getDashboardTaxUploadDraftState" in body
    assert "dashboardTaxUploadInitialDraftState = isEditMode" in body
    assert "setDashboardTaxUploadEventLocked" in body
    assert "dashboardTaxUploadEventTrigger.disabled = isLocked" in body
    assert "活動不可在編輯時修改。" in body
    assert "setDashboardTaxUploadEventLocked(isEditMode)" in body
    assert "taxReceiptUploadImportMessageType" in body
    assert "const adminEventsApiPath = \"/api/v1/admin/events\"" in body
    assert "const portalCsrfToken = portalPage.dataset.portalCsrfToken ?? \"\"" in body
    assert "submitDashboardEventForm" in body
    assert "dashboardEventFormSubmitButton?.addEventListener(\"click\"" in body
    assert "\"X-Portal-CSRF-Token\": portalCsrfToken" in body
    assert "const idempotencyKey = isEditMode ? \"\" : buildDashboardIdempotencyKey()" in body
    assert "\"Idempotency-Key\": idempotencyKey" in body
    assert "ipg:tax-receipt-upload:import" in body
    assert "ipg:tax-receipt-upload:open" in body
    assert "eventName: getDashboardTaxUploadEventName()" in body
    assert "file: selectedFile ?? null" in body
    assert "generatedAt: validatedData.generatedAt" in body
    assert "rowId: dashboardTaxUploadEditingRowId" in body
    assert "taxId: validatedData.taxId" in body
    assert "儲存變更" in body
    assert "image/png" in body
    assert ".webp" not in body
    assert "setDashboardEventDialogMode" in body
    assert "applyDashboardEventStatusValue" in body
    assert 'eventData.status ?? (isEditMode ? "open" : "unlisted")' in body
    assert "dashboardEventStatusCheckbox" in body
    assert "openDashboardEventStatusSelect" not in body
    assert "closeDashboardEventStatusSelect" not in body
    assert "collectDashboardEventDialogState" in body
    assert "dashboardEventStartDateInput" in body
    assert "dashboardEventEndDateInput" in body
    assert "dashboardEventCompletionHoursInput" in body
    assert "eventStartDate" in body
    assert "eventEndDate" in body
    assert "completionHours" in body
    assert "dashboardEventCompletionDownloadStartsAtInput" in body
    assert "dashboardEventCompletionDownloadToggle" in body
    assert "dashboardEventCompletionDocumentTypeOption" in body
    assert "completionCertDownloadStartsAt" in body
    assert "updateDashboardCompletionDownloadStartsAtVisibility" in body
    assert "hasRequiredDashboardCompletionCertFields" in body
    assert "readDashboardCompletionHoursInputValue()" in body
    assert "completionCertEnabled ? readDashboardCompletionHoursInputValue() : null" not in body
    assert "toggleDashboardCompletionCertDocumentType" in body
    assert "dashboardEventCompletionDownloadToggle?.addEventListener(\"click\"" in body
    assert "dashboardEventCompletionDownloadToggle?.addEventListener(\"keydown\"" in body
    assert "dashboardEventCompletionDocumentTypeOption?.addEventListener(\"click\"" in body
    assert "event.target !== dashboardEventCompletionDocumentTypeOption" in body
    assert "completionCertInput.dispatchEvent(new Event(\"change\", { bubbles: true }))" in body
    assert "window.iPlaygroundPortalDateTime" in body
    assert "formatCurrentDateTimeInputValue" in body
    assert "formatIsoDateInputValue" in body
    assert "formatUtcIsoDateTimeInputValue" in body
    assert "normalizeDateInputValue" in body
    assert "normalizeDateTimeInputValue" in body
    assert "installDatePicker" in body
    assert "installDateTimePicker" in body
    assert "function installDateTimePicker" not in body
    assert "function padDateTimePart" not in body
    assert "function parseDisplayDateTimeValue" not in body
    assert "textInput.type = \"datetime-local\"" not in body
    assert "select.id = `portal-completion-upload-map-${field.key}`" in body
    assert "installDateTimePicker(dashboardEventCompletionDownloadStartsAtInput)" in body
    assert "installDatePicker(dashboardEventStartDateInput)" in body
    assert "installDatePicker(dashboardEventEndDateInput)" in body
    assert "installDateTimePicker(dashboardTaxUploadGeneratedAtInput, { includeSeconds: true })" in body
    assert "dashboardEventDocumentTypeInputs.forEach" in body
    assert "updateDashboardEventFormSubmitState" in body
    assert "dashboardEventNameInput?.addEventListener(\"input\"" in body
    assert "confirmDashboardEventDialogClose" in body
    assert "資料尚未存檔，確定要取消嗎？" in body
    assert "closeDashboardEventCreateDialog" in body
    assert "ipg:event-form:open" in body
    assert "ipg:event-row:remove" in body
    assert "replaceEventId: pendingEventId" in body
    assert "buildDashboardPendingEventId" in body
    assert "contentFrame.contentWindow.location.reload()" not in body
    assert "window.alert(error instanceof Error ? error.message" not in body
    assert "ipg:completion-upload:open" in body
    assert "readDashboardCompletionUploadFieldMapping" in body
    assert "fieldMapping: readDashboardCompletionUploadFieldMapping()" in body
    assert "儲存變更" in body
    assert 'pageShell?.setAttribute("inert", "")' in body
    assert 'pageShell?.setAttribute("aria-hidden", "true")' in body
    assert 'contentFrame.src = targetButton.dataset.viewPath ?? welcomePagePath' in body
    assert "contentFrame.addEventListener" in body
    assert "button.dataset.viewTarget" in body
    assert "button.dataset.viewPath" in body
    assert 'window.location.assign(logoutUrl)' in body
    assert 'window.location.assign(portalEntryPath)' in body
    assert "contentFrame.contentWindow?.location?.pathname" in body
    assert "window.iPlaygroundPortalAuth?.redirectToPortalEntry" in body
    assert "window.iPlaygroundPortalEvents" in body
    assert "preload" in body
    assert "upsertCachedEvent" in body
    assert "renderDashboardTaxUploadEventSelect" in body


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
    assert 'document.getElementById("completion-upload-mapping")' in body
    assert "readCompletionUploadFieldMapping" in body
    assert "fieldMapping" in body
    assert '"completion-upload-event-trigger"' in body
    assert 'document.getElementById("completion-select-all")' not in body
    assert 'document.getElementById("completion-bulk-downloadable")' in body
    assert 'document.getElementById("completion-bulk-blocked")' in body
    assert 'document.getElementById("completion-pagination")' in body
    assert 'document.getElementById("completion-page-prev")' in body
    assert 'document.getElementById("completion-page-next")' in body
    assert 'document.getElementById("completion-page-status")' in body
    assert "const completionCertRowsPerPage = 10" in body
    assert "getCurrentCompletionCertPageRows" in body
    assert "visibleRows.slice(startIndex, startIndex + completionCertRowsPerPage)" in body
    assert "goToCompletionPage(completionCurrentPage - 1)" in body
    assert "goToCompletionPage(completionCurrentPage + 1)" in body
    assert "updateCompletionUploadFileName" in body
    assert "isCompletionCsvFile" in body
    assert "completionUploadImportMessageType" in body
    assert "ipg:completion-upload:import" in body
    assert "完訓證明資料匯入中..." in body
    assert "getCompletionUploadEventName" in body
    assert "applyCompletionUploadEventValue" in body
    assert "getFirstCompletionUploadEventValue" in body
    assert "loadingCompletionCertRowsMessage" in body
    assert "emptyCompletionCertRowsMessage" in body
    assert "isLoadingCompletionCertRows = true" in body
    assert "isLoadingCompletionCertRows = false" in body
    assert "openCompletionUploadEventSelect" in body
    assert "closeCompletionUploadEventSelect" in body
    assert "getVisibleCompletionCertRows" in body
    assert "message.eventId" in body
    assert "message.completionCerts" in body
    assert "parseCompletionCsv" in body
    assert "buildCompletionCertRows" in body
    assert "姓名 Full Name" in body
    assert "你是誰，ID 或具有鑑識度的名稱 Name on Badge" in body
    assert "服務單位（將顯示於 Badge 上）Organization / Company (will appear on Badge)" in body
    assert "kktixId" in body
    assert "badgeName" in body
    assert "organization" in body
    assert '"Id"' in body
    assert "Email" in body
    assert "email" in body
    assert "票券編號" not in body
    assert "票券名稱" not in body
    assert "訂購人姓名" not in body
    assert "電子信箱" not in body
    assert "renderCompletionCertRows" in body
    assert "importCompletionCsvText" in body
    assert "handleCompletionUploadDrop" in body
    assert "assignCompletionUploadFile" in body
    assert "document.addEventListener(\"drop\", handleCompletionUploadDrop)" in body
    assert "setCompletionRowDownloadState" in body
    assert 'isCheckedIn: attendanceStatus === "checkedIn"' in body
    assert 'isDownloadable: certStatus === "issued"' in body
    assert 'isDownloadable: rowData?.attendanceStatus === "checkedIn"' not in body
    assert "switchInput.checked = rowData.isCheckedIn" in body
    assert "switchInput.checked = rowData.isDownloadable" not in body
    assert "(row) => row.isCheckedIn !== isDownloadable" in body
    assert "isUpdatingCompletionBulkAttendance" in body
    assert "updateCompletionTableBusyState" in body
    assert "\"is-bulk-updating\"" in body
    assert "\"aria-busy\"" in body
    assert "openCompletionEditDialog" in body
    assert "submitCompletionEditDialog" in body
    assert 'document.getElementById("completion-edit-dialog")' in body
    assert 'document.getElementById("completion-edit-submit")' in body
    assert "setCompletionEditStaticValue" in body
    assert "completionEditName?.focus()" in body
    assert "showCompletionPageAlert" in body
    assert "window.iPlaygroundPageAlert?.show" in body
    assert "完訓證明資料已更新。" in body
    assert "更新成功" in body
    assert "encodeURIComponent(rowData.id)" in body
    assert "method: \"PUT\"" in body
    assert "setCompletionSelectionForAllRows" not in body
    assert "applyDownloadableStateToSelection" not in body
    assert "applyDownloadableStateToCurrentActivity" in body
    assert "switchInput.disabled = isUpdatingCompletionBulkAttendance" in body
    assert "editButton.disabled = isUpdatingCompletionBulkAttendance" in body
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
    assert "window.iPlaygroundPortalEvents" in body
    assert "getCachedEvents" in body
    assert "refresh" in body
    assert "ipg:portal-events:updated" in body
    assert "handlePortalUnauthorizedResponse" in body
    assert "verifyPortalSession" in body


def test_portal_dashboard_completion_reviews_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard-completion-reviews.js",
            route_params={"asset_name": "portal-dashboard-completion-reviews.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.getElementById("completion-review-refresh")' in body
    assert 'document.getElementById("completion-review-table-body")' in body
    assert 'document.getElementById("completion-review-dialog")' in body
    assert '"/api/v1/admin/completion-cert-change-requests"' in body
    assert "loadCompletionReviews" in body
    assert "openCompletionReviewDialog" in body
    assert "submitCompletionReview" in body
    assert "status === \"approved\"" in body
    assert "payload.email" not in body
    assert "修改申請已通過並更新資料。" in body
    assert "修改申請已駁回。" in body
    assert "X-Portal-CSRF-Token" in body
    assert "handlePortalUnauthorizedResponse" in body
    assert "targetWindow.location.assign(portalEntryPath)" in body
    assert "portalSessionStartedAtKey" in body
    assert "portalSessionMaxAgeMs" in body
    assert "verifyPortalSession" in body


def test_portal_dashboard_tax_receipts_js_asset_returns_expected_content_type() -> None:
    response = static_asset(
        build_request(
            "http://localhost:7075/assets/portal-dashboard-tax-receipts.js",
            route_params={"asset_name": "portal-dashboard-tax-receipts.js"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert 'document.getElementById("tax-upload-open")' in body
    assert 'document.getElementById("tax-upload-title")' in body
    assert 'document.getElementById("tax-upload-continue")' in body
    assert 'document.getElementById("tax-upload-file-name")' in body
    assert 'document.getElementById("tax-upload-submit")' in body
    assert 'document.getElementById("tax-upload-tax-id")' in body
    assert 'document.getElementById("tax-upload-amount")' in body
    assert 'document.getElementById("tax-upload-generated-at")' in body
    assert 'document.getElementById("tax-upload-errors")' in body
    assert 'document.getElementById("tax-upload-event")' in body
    assert '"tax-upload-event-trigger"' in body
    assert 'document.getElementById("tax-bulk-downloadable")' not in body
    assert 'document.getElementById("tax-bulk-blocked")' not in body
    assert "updateTaxUploadFileName" in body
    assert "isTaxReceiptUploadFile" in body
    assert "validateTaxUploadForm" in body
    assert "invalidTaxUploadTaxIdMessage" in body
    assert "invalidTaxUploadAmountMessage" in body
    assert "請輸入大於 0 的整數金額。" in body
    assert "invalidTaxUploadGeneratedAtMessage" in body
    assert "taxReceiptUploadImportMessageType" in body
    assert "ipg:tax-receipt-upload:import" in body
    assert "ipg:tax-receipt-upload:open" in body
    assert "setTaxUploadDialogMode" in body
    assert "taxUploadTaxIdInput.readOnly = isEditMode" in body
    assert "統編不可修改；如需更正請刪除後重新新增。" in body
    assert "taxUploadInitialDraftState" in body
    assert "getTaxUploadDraftState" in body
    assert "taxUploadInitialDraftState = isEditMode" in body
    assert "setTaxUploadEventLocked" in body
    assert "taxUploadEventTrigger.disabled = isLocked" in body
    assert "活動不可在編輯時修改。" in body
    assert "setTaxUploadEventLocked(isEditMode)" in body
    assert "handleTaxUploadDrop" in body
    assert "assignTaxUploadFile" in body
    assert "document.addEventListener(\"drop\", handleTaxUploadDrop)" in body
    assert "shouldContinueTaxUpload" in body
    assert "resetTaxUploadFieldsForNextFile" in body
    assert "getTaxUploadEventName" in body
    assert "applyTaxUploadEventValue" in body
    assert "openTaxUploadEventSelect" in body
    assert "closeTaxUploadEventSelect" in body
    assert "getVisibleTaxReceiptRows" in body
    assert "message.eventName" in body
    assert "message.taxId" in body
    assert "message.amount" in body
    assert "message.generatedAt" in body
    assert "renderTaxReceiptRows" in body
    assert 'document.getElementById("tax-receipt-pagination")' in body
    assert 'document.getElementById("tax-receipt-page-prev")' in body
    assert 'document.getElementById("tax-receipt-page-status")' in body
    assert 'document.getElementById("tax-receipt-page-next")' in body
    assert "const taxReceiptRowsPerPage = 10" in body
    assert "visibleRows.slice(startIndex, startIndex + taxReceiptRowsPerPage)" in body
    assert "updateTaxReceiptPaginationControls" in body
    assert "goToTaxReceiptPage(taxReceiptCurrentPage - 1)" in body
    assert "goToTaxReceiptPage(taxReceiptCurrentPage + 1)" in body
    assert 'document.getElementById("tax-id-filter")' in body
    assert "getTaxIdFilterValue" in body
    assert "emptyTaxReceiptSearchRowsMessage" in body
    assert "查無符合統編的繳稅證明。" in body
    assert "row.taxId.includes(taxIdQuery)" in body
    assert 'taxIdFilter?.addEventListener("input"' in body
    assert "adminTaxReceiptsApiPath" in body
    assert "buildPendingTaxReceiptRow" in body
    assert "insertPendingTaxReceiptRow" in body
    assert "replacePendingTaxReceiptRow" in body
    assert "removePendingTaxReceiptRow" in body
    assert "rowElement.classList.toggle(\"is-disabled\", Boolean(rowData.isPending))" in body
    assert "檔案正在新增中" in body
    assert "saveTaxReceiptFile" in body
    assert "upsertTaxReceiptRow" in body
    assert "showTaxReceiptPageAlert" in body
    assert "新增成功" in body
    assert "繳稅證明資料已新增。" in body
    assert "loadTaxReceiptRows" in body
    assert "loadingTaxReceiptRowsMessage" in body
    assert "isLoadingTaxReceiptRows" in body
    assert "taxReceiptRowsMessageOverride" in body
    assert "emptyTaxReceiptRowsMessage" in body
    assert "taxReceiptDownloadApiPath" in body
    assert "downloadTaxReceiptBlob" in body
    assert "downloadingTaxReceiptMessage" in body
    assert "正在準備繳稅證明檔案，請稍候。" in body
    assert "setTaxReceiptDownloadButtonBusy" in body
    assert "下載中..." in body
    assert "下載已開始" in body
    assert "下載失敗" in body
    assert "downloadButton.setAttribute(\"aria-busy\", String(isBusy))" in body
    assert "deleteTaxReceiptRow" in body
    assert "openTaxEditDialog" in body
    assert "setTaxReceiptRowDownloadState" not in body
    assert "applyTaxDownloadableStateToCurrentActivity" not in body
    assert "URL.createObjectURL(file)" not in body
    assert "URL.createObjectURL(fileBlob)" in body
    assert "URL.revokeObjectURL(objectUrl)" in body
    assert "確定要刪除此筆繳稅證明嗎？" in body
    assert "儲存變更" in body
    assert "formatTaxGeneratedAt" in body
    assert "window.iPlaygroundPortalDateTime" in body
    assert "formatCurrentDateTimeInputValue" in body
    assert "formatUtcIsoDateTimeInputValue" in body
    assert "normalizeDateTimeInputValue" in body
    assert "installDateTimePicker" in body
    assert "function installDateTimePicker" not in body
    assert "function padDateTimePart" not in body
    assert "function parseDisplayDateTimeValue" not in body
    assert "textInput.type = \"datetime-local\"" not in body
    assert "document.createElement(\"select\")" not in body
    assert "installDateTimePicker(taxUploadGeneratedAtInput, { includeSeconds: true })" in body
    assert "可下載" not in body
    assert "停用" not in body
    assert "CSV" not in body
    assert ".csv" not in body
    assert "window.iPlaygroundPortalEvents" in body
    assert "renderTaxEventSelects" in body
    assert "loadTaxEvents" in body
    assert "handlePortalUnauthorizedResponse" in body
    assert "verifyPortalSession" in body


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
    assert "handlePortalUnauthorizedResponse" in body
    assert "verifyPortalSession" in body
    assert "openEventCreateDialog" in body
    assert "openEventEditDialog" in body
    assert "setEventDialogMode" in body
    assert "applyEventStatusValue" in body
    assert 'eventData.status ?? (isEditMode ? "open" : "unlisted")' in body
    assert "eventStatusCheckbox" in body
    assert "openEventStatusSelect" not in body
    assert "closeEventStatusSelect" not in body
    assert "collectEventDialogState" in body
    assert "eventStartDateInput" in body
    assert "eventEndDateInput" in body
    assert "eventCompletionHoursInput" in body
    assert "eventStartDate" in body
    assert "eventEndDate" in body
    assert "completionHours" in body
    assert "eventCompletionDownloadStartsAtInput" in body
    assert "eventCompletionDownloadToggle" in body
    assert "const adminEventsApiPath = \"/api/v1/admin/events\"" in body
    assert "const portalCsrfToken = document.body.dataset.portalCsrfToken ?? \"\"" in body
    assert "submitEventForm" in body
    assert "eventFormSubmitButton?.addEventListener(\"click\"" in body
    assert "\"X-Portal-CSRF-Token\": portalCsrfToken" in body
    assert "const idempotencyKey = isEditMode ? \"\" : buildEventIdempotencyKey()" in body
    assert "\"Idempotency-Key\": idempotencyKey" in body
    assert "eventCompletionDocumentTypeOption" in body
    assert "completionCertDownloadStartsAt" in body
    assert "updateCompletionDownloadStartsAtVisibility" in body
    assert "hasRequiredCompletionCertFields" in body
    assert "readCompletionHoursInputValue()" in body
    assert "completionCertEnabled ? readCompletionHoursInputValue() : null" not in body
    assert "toggleCompletionCertDocumentType" in body
    assert "eventCompletionDownloadToggle?.addEventListener(\"click\"" in body
    assert "eventCompletionDownloadToggle?.addEventListener(\"keydown\"" in body
    assert "eventCompletionDocumentTypeOption?.addEventListener(\"click\"" in body
    assert "event.target !== eventCompletionDocumentTypeOption" in body
    assert "completionCertInput.dispatchEvent(new Event(\"change\", { bubbles: true }))" in body
    assert "window.iPlaygroundPortalDateTime" in body
    assert "formatCurrentDateTimeInputValue" in body
    assert "formatIsoDateInputValue" in body
    assert "formatUtcIsoDateTimeInputValue" in body
    assert "normalizeDateInputValue" in body
    assert "normalizeDateTimeInputValue" in body
    assert "installDatePicker" in body
    assert "installDateTimePicker" in body
    assert "function installDateTimePicker" not in body
    assert "function padDateTimePart" not in body
    assert "function parseDisplayDateTimeValue" not in body
    assert "textInput.type = \"datetime-local\"" not in body
    assert "document.createElement(\"select\")" not in body
    assert "installDateTimePicker(eventCompletionDownloadStartsAtInput)" in body
    assert "installDatePicker(eventStartDateInput)" in body
    assert "installDatePicker(eventEndDateInput)" in body
    assert "updateEventFormSubmitState" in body
    assert "eventNameInput?.addEventListener(\"input\"" in body
    assert "confirmEventDialogClose" in body
    assert "資料尚未存檔，確定要取消嗎？" in body
    assert "closeEventCreateDialog" in body
    assert "requestParentEventFormDialog" in body
    assert "window.parent.postMessage" in body
    assert "window.parent !== window" in body
    assert "loadEventRows" in body
    assert "renderEventRows" in body
    assert "buildEventRow" in body
    assert "row.dataset.eventFormOpen = \"edit\"" in body
    assert "resolveEventDocumentTypeItems" in body
    assert "document-type-pill-list" in body
    assert "document-type-pill" in body
    assert "is-completion-cert" in body
    assert "is-tax-receipt" in body
    assert "event-status-badge is-open" in body
    assert "event-status-badge is-unlisted" in body
    assert "insertPendingEventRow" in body
    assert "buildPendingEventRow" in body
    assert "removeEventRow" in body
    assert "replaceEventId: pendingEventId" in body
    assert "ipg:event-row:remove" in body
    assert "儲存變更" in body
    assert 'event.key !== "Enter" && event.key !== " "' in body
    assert "eventCreateDialog.hidden = false" in body
    assert "eventCode" not in body
    assert 'event.key === "Escape"' in body
    assert "window.iPlaygroundPortalEvents" in body
    assert "getCachedEvents" in body
    assert "refresh" in body
    assert "upsertCachedEvent" in body


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
    assert 'const welcomeMetricsApiPath = "/api/v1/admin/dashboard/welcome-metrics"' in body
    assert "loadWelcomeMetrics" in body
    assert "formatMetricCurrency" in body
    assert "taxReceipt.totalAmount" in body
    assert "taxReceipt.queriedCompanyCount" in body
    assert "updateMetricSource" in body
    assert "資料來源：完訓證明" in body
    assert "資料來源：營業稅繳稅證明" in body
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
