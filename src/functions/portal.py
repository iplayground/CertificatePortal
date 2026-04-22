from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import azure.functions as func

blueprint = func.Blueprint()

PORTAL_LOGIN_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_login.html"
PORTAL_DASHBOARD_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "portal_dashboard.html"
PORTAL_DASHBOARD_WELCOME_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_welcome.html"
)
PORTAL_DASHBOARD_RECORDS_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_records.html"
)
PORTAL_DASHBOARD_UPLOAD_TEMPLATE_PATH = (
    Path(__file__).resolve().parent / "templates" / "portal_dashboard_upload.html"
)


@lru_cache(maxsize=1)
def load_portal_login_template() -> str:
    return PORTAL_LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_template() -> str:
    return PORTAL_DASHBOARD_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_welcome_template() -> str:
    return PORTAL_DASHBOARD_WELCOME_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_records_template() -> str:
    return PORTAL_DASHBOARD_RECORDS_TEMPLATE_PATH.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_portal_dashboard_upload_template() -> str:
    return PORTAL_DASHBOARD_UPLOAD_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_portal_page_response(template: str) -> func.HttpResponse:
    return func.HttpResponse(
        body=template,
        status_code=200,
        mimetype="text/html",
        charset="utf-8",
        headers={
            "Content-Language": "zh-TW",
            "Cache-Control": "no-store",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )


@blueprint.function_name(name="portal_login_page")
@blueprint.route(
    route="portal",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_login_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return build_portal_page_response(load_portal_login_template())


@blueprint.function_name(name="portal_dashboard_page")
@blueprint.route(
    route="portal/dashboard",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return build_portal_page_response(load_portal_dashboard_template())


@blueprint.function_name(name="portal_dashboard_welcome_page")
@blueprint.route(
    route="portal/dashboard/welcome",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_welcome_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return build_portal_page_response(load_portal_dashboard_welcome_template())


@blueprint.function_name(name="portal_dashboard_records_page")
@blueprint.route(
    route="portal/dashboard/records",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_records_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return build_portal_page_response(load_portal_dashboard_records_template())


@blueprint.function_name(name="portal_dashboard_upload_page")
@blueprint.route(
    route="portal/dashboard/upload",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def portal_dashboard_upload_page(req: func.HttpRequest) -> func.HttpResponse:
    del req

    return build_portal_page_response(load_portal_dashboard_upload_template())
