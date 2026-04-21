from __future__ import annotations

import azure.functions as func

from src.functions.assets import static_asset
from src.functions.home import home_page


def test_home_page_returns_html_with_expected_fields() -> None:
    request = func.HttpRequest(
        method="GET",
        url="http://localhost:7075/",
        headers={},
        params={},
        route_params={},
        body=b"",
    )

    response = home_page(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "iPlayground 2026" in body
    assert "報名人姓名" in body
    assert "會眾姓名" not in body
    assert "email" in body
    assert "請輸入您的報名人姓名" in body
    assert "本網站內容與相關資料之著作權均屬社團法人台北市頂尖軟體開發者協會(77212283)所有" in body
    assert "Azure Functions 線上頁面已啟用" not in body
    assert 'src="/assets/logo_b_alpha.png"' in body
    assert "iPlayground Certify" not in body
    assert 'class="custom-select-trigger"' in body
    assert 'name="viewport"' in body
    assert 'href="/assets/home.css"' in body
    assert 'src="/assets/home.js"' in body


def test_home_css_asset_returns_expected_content_type() -> None:
    request = func.HttpRequest(
        method="GET",
        url="http://localhost:7075/assets/home.css",
        headers={},
        params={},
        route_params={"asset_name": "home.css"},
        body=b"",
    )

    response = static_asset(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert "@media (max-width: 640px)" in body
    assert ".custom-select-menu[hidden]" in body


def test_home_js_asset_returns_expected_content_type() -> None:
    request = func.HttpRequest(
        method="GET",
        url="http://localhost:7075/assets/home.js",
        headers={},
        params={},
        route_params={"asset_name": "home.js"},
        body=b"",
    )

    response = static_asset(request)
    body = response.get_body().decode("utf-8")

    assert response.status_code == 200
    assert response.mimetype == "application/javascript"
    assert "previewAction.addEventListener" in body
    assert "closeEventNameSelect" in body
    assert "eventNameTrigger.blur()" in body


def test_logo_asset_returns_png_bytes() -> None:
    request = func.HttpRequest(
        method="GET",
        url="http://localhost:7075/assets/logo_b_alpha.png",
        headers={},
        params={},
        route_params={"asset_name": "logo_b_alpha.png"},
        body=b"",
    )

    response = static_asset(request)
    body = response.get_body()

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert body.startswith(b"\x89PNG")
