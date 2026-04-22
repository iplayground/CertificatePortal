from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import azure.functions as func

blueprint = func.Blueprint()

PORTAL_LOGIN_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_login.html"


@lru_cache(maxsize=1)
def load_portal_login_template() -> str:
    return PORTAL_LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")


@blueprint.function_name(name="portal_login_page")
@blueprint.route(
    route="portal",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_login_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return func.HttpResponse(
        body=load_portal_login_template(),
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers={
            "Content-Language": "zh-TW",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
