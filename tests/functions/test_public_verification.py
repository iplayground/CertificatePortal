from __future__ import annotations

import azure.functions as func

from src.functions.public_verification import verify_cert_page


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


def test_verify_page_defaults_to_traditional_chinese() -> None:
    response = verify_cert_page(build_request("demo-cert"))
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert response.headers["Content-Language"] == "zh-TW"
    assert "iPlayground 完訓證明驗證頁面" in body
    assert "status: 尚未串接實際驗證資料" in body


def test_verify_page_uses_accept_language_without_cookie() -> None:
    response = verify_cert_page(
        build_request(
            "demo-cert",
            headers={"Accept-Language": "en-US,en;q=0.9"},
        )
    )
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.headers["Content-Language"] == "en-US"
    assert "iPlayground Certificate Verification" in body
    assert "status: Verification data is not connected yet" in body


def test_verify_page_prefers_cookie_locale_over_accept_language() -> None:
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
    assert "iPlayground Certificate Verification" in body
    assert "iPlayground 完訓證明驗證頁面" not in body
