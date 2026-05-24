from __future__ import annotations

from typing import Any

import azure.functions as func

from src.functions.assets import static_asset
from src.functions import public_verification
from src.functions.public_verification import verify_cert_page
from src.shared.completion_store import CompletionStoreConfigurationError


class FakeCompletionContainer:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = documents

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        enable_cross_partition_query: bool,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        token = next(
            parameter["value"]
            for parameter in parameters or []
            if parameter["name"] == "@verificationToken"
        )
        return [
            document.copy()
            for document in self.documents
            if document.get("verificationTokenHash") == token
            and document.get("certStatus") == "issued"
        ][:1]

    def read_item(self, item: str, partition_key: str, **_: Any) -> dict[str, Any]:
        for document in self.documents:
            if document["id"] == item and document["eventId"] == partition_key:
                return document.copy()

        raise FakeCosmosNotFoundError()

    def replace_item(self, item: str, body: dict[str, Any], **_: Any) -> dict[str, Any]:
        for index, document in enumerate(self.documents):
            if document["id"] == item:
                self.documents[index] = body.copy()
                return self.documents[index]

        raise FakeCosmosNotFoundError()


class FakeEventContainer:
    def __init__(self, documents: dict[str, dict[str, Any]]) -> None:
        self.documents = documents

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        document = self.documents.get(item)
        if document is None:
            raise FakeCosmosNotFoundError()
        return document

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        self.documents[item] = body.copy()
        return self.documents[item]


class FakeCosmosNotFoundError(Exception):
    status_code = 404


def build_request(
    cert_id: str,
    *,
    headers: dict[str, str] | None = None,
) -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url=f"http://localhost:7075/verify/{cert_id}",
        headers=headers or {},
        params={},
        route_params={"certId": cert_id},
        body=b"",
    )


def test_verify_page_defaults_to_traditional_chinese(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        lambda: FakeCompletionContainer([]),
    )

    response = verify_cert_page(build_request("demo-cert"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.headers["Content-Language"] == "zh-TW"
    assert response.headers["Cache-Control"] == "no-store"
    assert "<html lang=\"zh-TW\">" in body
    assert "無法驗證此證明" in body
    assert 'class="verify-page verify-page--invalid"' in body
    assert 'data-current-locale="zh-TW"' in body
    assert 'class="brand-row"' in body
    assert 'class="brand-logo" id="brand-logo" src="/assets/logo_b_alpha.png?v=' in body
    assert 'class="locale-switcher" id="locale-switcher"' in body
    assert 'aria-label="語系"' in body
    assert 'data-locale="zh-TW"' in body
    assert 'data-locale="en-US"' in body
    assert '<script src="/assets/locale-switcher.js?v=' in body
    assert '<script id="verify-page-i18n" type="application/json">' in body
    assert '<p class="status-label">驗證狀態</p>' not in body
    assert "證明編號" in body
    assert "證明姓名" in body
    assert "活動" in body
    assert "發證時間" in body
    assert 'data-detail-key="organization"' not in body
    assert body.count('<dd class="verification-detail-value">未顯示</dd>') == 4
    assert body.index("證明編號") < body.index("活動") < body.index("證明姓名")
    assert 'class="home-action" id="home-action" href="/"' in body
    assert "support@iplayground.io" in body
    assert "尚未串接實際驗證資料" not in body


def test_verify_page_uses_accept_language_without_cookie(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        lambda: FakeCompletionContainer([]),
    )

    response = verify_cert_page(
        build_request(
            "demo-cert",
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "en-US"
    assert "<html lang=\"en-US\">" in body
    assert "This certificate cannot be verified" in body
    assert 'data-current-locale="en-US"' in body
    assert 'aria-label="Language"' in body


def test_verify_page_prefers_cookie_locale_over_accept_language(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        lambda: FakeCompletionContainer([]),
    )

    response = verify_cert_page(
        build_request(
            "demo-cert",
            headers={
                "Cookie": "ipg_locale=en-US",
                "Accept-Language": "zh-TW,zh;q=0.9",
            },
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "en-US"
    assert "This certificate cannot be verified" in body
    assert '<h1 id="verify-title">無法驗證此證明</h1>' not in body


def test_verify_page_renders_valid_completion_certificate(
    monkeypatch: Any,
) -> None:
    events_container = FakeEventContainer(
        {
            "evt_1": {
                "id": "evt_1",
                "name": "iPlayground 2026",
                "metrics": {
                    "completionCert": {
                        "totalCount": 1,
                        "downloadableCount": 1,
                        "downloadCount": 1,
                        "verificationCount": 2,
                    }
                },
            }
        }
    )
    records_container = FakeCompletionContainer(
        [
            {
                "id": "ccert_1",
                "eventId": "evt_1",
                "number": 12,
                "kktixId": "KKTIX-001",
                "certStatus": "issued",
                "verificationTokenHash": "valid-token",
                "verificationCount": 2,
                "certificateDisplayName": "王小明",
                "certificateDisplayOrganization": "iPlayground",
                "certificateLocale": "zh-TW",
                "issuedAt": "2026-05-01T08:00:00Z",
            }
        ]
    )
    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        lambda: records_container,
    )
    monkeypatch.setattr(
        public_verification,
        "get_events_container",
        lambda: events_container,
    )

    response = verify_cert_page(build_request("valid-token"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "此完訓證明有效" in body
    assert 'class="verify-page verify-page--valid"' in body
    assert '<p class="status-label">驗證狀態</p>' not in body
    assert "KKTIX-001-12" in body
    assert "王小明" in body
    assert "iPlayground 2026" in body
    assert body.index("證明編號") < body.index("活動") < body.index("證明姓名")
    assert "發證時間" in body
    assert '<script src="/assets/locale-switcher.js?v=' in body
    assert '<script src="/assets/verify.js?v=' in body
    assert 'data-detail-key="status"' in body
    assert 'data-detail-key="issuedAt"' in body
    assert '<time class="local-datetime" datetime="2026-05-01T08:00:00Z">' in body
    assert "2026 / 05 / 01 08:00 UTC" in body
    assert "valid-token" not in body
    assert records_container.documents[0]["verificationCount"] == 3
    assert records_container.documents[0]["updatedAt"].endswith("Z")
    assert events_container.documents["evt_1"]["metrics"]["completionCert"] == {
        "totalCount": 1,
        "downloadableCount": 1,
        "downloadCount": 1,
        "verificationCount": 3,
    }


def test_verify_js_updates_locale_without_reloading() -> None:
    response = static_asset(
        func.HttpRequest(
            method="GET",
            url="http://localhost:7075/assets/verify.js",
            headers={},
            params={},
            route_params={"asset_name": "verify.js"},
            body=b"",
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "parseVerifyPageI18n" in body
    assert "applyLocaleSelection" in body
    assert "applyVerifyPageLocale" in body
    assert "onSelect: applyLocaleSelection" in body
    assert "document.title = copy.page_title" in body
    assert "htmlRoot.lang = bundle.html_lang" in body
    assert "updateDetailLabels" in body


def test_verify_page_hides_organization_when_certificate_did_not_show_it(
    monkeypatch: Any,
) -> None:
    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        lambda: FakeCompletionContainer(
            [
                {
                    "id": "ccert_1",
                    "eventId": "evt_1",
                    "number": 12,
                    "kktixId": "KKTIX-001",
                    "certStatus": "issued",
                    "verificationTokenHash": "valid-token",
                    "certificateDisplayName": "王小明",
                    "certificateDisplayOrganization": "",
                    "certificateLocale": "zh-TW",
                    "issuedAt": "2026-05-01T08:00:00Z",
                }
            ]
        ),
    )
    monkeypatch.setattr(
        public_verification,
        "get_events_container",
        lambda: FakeEventContainer({"evt_1": {"id": "evt_1", "name": "iPlayground 2026"}}),
    )

    response = verify_cert_page(build_request("valid-token"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "此完訓證明有效" in body
    assert 'data-detail-key="organization"' not in body
    assert "發證時間" in body


def test_verify_page_uses_unavailable_state_when_store_is_not_configured(
    monkeypatch: Any,
) -> None:
    def raise_configuration_error() -> None:
        raise CompletionStoreConfigurationError("missing config")

    monkeypatch.setattr(
        public_verification,
        "get_completion_records_container",
        raise_configuration_error,
    )

    response = verify_cert_page(build_request("valid-token"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert "暫時無法完成驗證" in body
    assert "驗證服務目前暫時不可用" in body
