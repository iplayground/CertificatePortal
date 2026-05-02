from __future__ import annotations

import azure.functions as func
import pytest

from src.functions import health
from src.functions.health import health_api


def build_request() -> func.HttpRequest:
    return func.HttpRequest(
        method="GET",
        url="http://localhost/api/health",
        headers={},
        params={},
        route_params={},
        body=b"",
    )


def test_health_api_returns_deployed_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    health.load_build_info.cache_clear()
    monkeypatch.setattr(health, "load_build_info", lambda: {"commit": "abc123"})

    response = health_api(build_request())

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert response.get_body() == b'{"status":"ok","commit":"abc123"}'
    assert response.headers["Cache-Control"] == "no-store"


def test_health_api_uses_empty_commit_when_build_info_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    health.load_build_info.cache_clear()
    monkeypatch.setattr(health, "BUILD_INFO_PATH", health.BUILD_INFO_PATH.parent / "missing.json")

    response = health_api(build_request())

    assert response.status_code == 200
    assert response.get_body() == b'{"status":"ok","commit":""}'
