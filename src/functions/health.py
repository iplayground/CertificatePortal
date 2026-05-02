from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import azure.functions as func

blueprint = func.Blueprint()

BUILD_INFO_PATH = Path(__file__).resolve().parents[2] / "build-info.json"


@lru_cache(maxsize=1)
def load_build_info() -> dict[str, Any]:
    if not BUILD_INFO_PATH.exists():
        return {}

    with BUILD_INFO_PATH.open(encoding="utf-8") as build_info_file:
        build_info = json.load(build_info_file)

    if not isinstance(build_info, dict):
        return {}

    return build_info


@blueprint.function_name(name="health_api")
@blueprint.route(
    route="api/health",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def health_api(req: func.HttpRequest) -> func.HttpResponse:
    build_info = load_build_info()
    commit = build_info.get("commit", "")

    if not isinstance(commit, str):
        commit = ""

    return func.HttpResponse(
        body=json.dumps(
            {
                "status": "ok",
                "commit": commit,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        status_code=200,
        mimetype="application/json",
        charset="utf-8",
        headers={"Cache-Control": "no-store"},
    )
