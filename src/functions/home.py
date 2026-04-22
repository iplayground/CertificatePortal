from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import azure.functions as func

from src.shared.i18n import get_home_page_context, localized_response_headers, resolve_locale
from src.shared.templates import render_html_template

blueprint = func.Blueprint()

HOME_PAGE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"


@lru_cache(maxsize=1)
def load_home_page_template() -> str:
    return HOME_PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_home_page_url_context(req: func.HttpRequest) -> dict[str, str]:
    page_url = _build_absolute_url(req, "/")

    return {
        "canonical_url": page_url,
        "page_url": page_url,
        "social_image_url": _build_absolute_url(req, "/assets/logo_sq_b.png"),
    }


def _build_absolute_url(req: func.HttpRequest, path: str) -> str:
    request_url = urlsplit(req.url)
    scheme = _resolve_forwarded_value(req, "X-Forwarded-Proto") or request_url.scheme or "https"
    host = _resolve_forwarded_value(req, "X-Forwarded-Host") or request_url.netloc
    normalized_path = path if path.startswith("/") else f"/{path}"

    return urlunsplit((scheme, host, normalized_path, "", ""))


def _resolve_forwarded_value(req: func.HttpRequest, header_name: str) -> str | None:
    header_value = req.headers.get(header_name)
    if not header_value:
        return None

    first_value = header_value.split(",", maxsplit=1)[0].strip()
    return first_value or None


@blueprint.function_name(name="home_page")
@blueprint.route(
    route="/",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def home_page(req: func.HttpRequest) -> func.HttpResponse:
    locale = resolve_locale(req)
    context = {
        **get_home_page_context(locale),
        **build_home_page_url_context(req),
    }
    html = render_html_template(
        load_home_page_template(),
        context,
    )

    return func.HttpResponse(
        body=html,
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers=localized_response_headers(locale),
    )
