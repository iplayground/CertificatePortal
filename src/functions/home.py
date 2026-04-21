from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import azure.functions as func

blueprint = func.Blueprint()

HOME_PAGE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"


@lru_cache(maxsize=1)
def load_home_page_html() -> str:
    return HOME_PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


@blueprint.function_name(name="home_page")
@blueprint.route(
    route="{x:regex(^$)?}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def home_page(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        body=load_home_page_html(),
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
    )
