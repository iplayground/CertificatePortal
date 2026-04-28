from __future__ import annotations

from functools import lru_cache
from html import escape
from json import dumps
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import azure.functions as func

from src.shared.event_store import (
    EventStoreConfigurationError,
    EventStoreOperationError,
    get_events_container,
    list_public_event_documents,
)
from src.shared.i18n import get_home_page_context, localized_response_headers, resolve_locale
from src.shared.templates import render_html_template

blueprint = func.Blueprint()

HOME_PAGE_TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "home.html"
HOME_ALLOWED_DOCUMENT_TYPES = frozenset({"completionCert", "taxReceipt"})


@lru_cache(maxsize=1)
def load_home_page_template() -> str:
    return HOME_PAGE_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_home_page_url_context(req: func.HttpRequest) -> dict[str, str]:
    page_url = _build_absolute_url(req, "/")

    return {
        "canonical_url": page_url,
        "events_api_path": "/api/v1/events",
        "page_url": page_url,
        "social_image_url": _build_absolute_url(req, "/assets/logo_sq_b.png"),
    }


def build_home_page_event_context(copy: dict[str, str]) -> dict[str, str]:
    events: list[dict[str, Any]] = []
    selected_event = events[0] if events else None
    selected_document_type = ""
    selected_document_type_label = copy["document_type_loading_option"]
    if selected_event is not None and selected_event["documentTypes"]:
        selected_document_type = selected_event["documentTypes"][0]
        selected_document_type_label = resolve_home_document_type_label(
            selected_document_type,
            copy,
        )

    if selected_event is None:
        selected_document_type = "completionCert"
    selected_event_document_types = selected_event["documentTypes"] if selected_event else None
    use_static_document_type = (
        selected_event_document_types is not None
        and len(selected_event_document_types) <= 1
    )

    return {
        "event_name_control_html": build_home_event_name_control_html(
            events,
            copy["event_name_loading_option"],
        ),
        "document_type_options_html": build_home_document_type_options_html(
            copy,
            selected_document_type,
            selected_event_document_types,
        ),
        "document_type_value": selected_document_type,
        "document_type_value_label": selected_document_type_label,
        "document_type_static_hidden_attr": "" if use_static_document_type else " hidden",
        "document_type_trigger_hidden_attr": " hidden" if use_static_document_type else "",
    }


def list_home_page_events() -> list[dict[str, Any]]:
    try:
        event_documents = list_public_event_documents(container=get_events_container())
    except (EventStoreConfigurationError, EventStoreOperationError):
        return []

    return normalize_home_event_documents(event_documents)


def normalize_home_event_documents(
    event_documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for event_document in event_documents:
        event_id = str(event_document.get("id", "")).strip()
        event_name = str(event_document.get("name", "")).strip()
        document_types = normalize_home_event_document_types(
            event_document.get("documentTypes")
        )
        if not event_id or not event_name:
            continue

        events.append(
            {
                "id": event_id,
                "name": event_name,
                "documentTypes": document_types,
            }
        )

    return events


def build_public_events_json_payload() -> dict[str, Any]:
    event_documents = list_public_event_documents(container=get_events_container())
    return {"events": normalize_home_event_documents(event_documents)}


def build_home_api_json_response(
    payload: dict[str, Any],
    *,
    status_code: int = 200,
) -> func.HttpResponse:
    return func.HttpResponse(
        body=dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status_code=status_code,
        mimetype="application/json",
        charset="utf-8",
        headers={
            "Cache-Control": "no-store",
        },
    )


def build_home_api_error_response(
    status_code: int,
    code: str,
    message: str,
) -> func.HttpResponse:
    return build_home_api_json_response(
        {
            "error": {
                "code": code,
                "message": message,
            },
        },
        status_code=status_code,
    )


def normalize_home_event_document_types(document_types: Any) -> list[str]:
    if not isinstance(document_types, list):
        return []

    normalized_document_types: list[str] = []
    for document_type in document_types:
        normalized_document_type = str(document_type).strip()
        if (
            normalized_document_type in HOME_ALLOWED_DOCUMENT_TYPES
            and normalized_document_type not in normalized_document_types
        ):
            normalized_document_types.append(normalized_document_type)

    return normalized_document_types


def build_home_event_name_control_html(
    events: list[dict[str, Any]],
    empty_event_name: str,
) -> str:
    if not events:
        return (
            '<input id="event-name" name="eventName" type="hidden" value="">'
            '<div class="field-static-value" id="event-name-value">'
            f"{escape(empty_event_name)}"
            "</div>"
        )

    selected_event = events[0]
    if len(events) == 1:
        return (
            '<input id="event-name" name="eventName" type="hidden" '
            f'value="{escape(selected_event["name"], quote=True)}" '
            f'data-event-id="{escape(selected_event["id"], quote=True)}" '
            "data-event-document-types="
            f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
            '<div class="field-static-value" id="event-name-value" '
            "data-event-document-types="
            f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
            f"{escape(selected_event['name'])}"
            "</div>"
        )

    options_html: list[str] = []
    for index, event in enumerate(events):
        selected_class = " is-selected" if index == 0 else ""
        aria_selected = "true" if index == 0 else "false"
        options_html.append(
            (
                f'<button class="custom-select-option{selected_class}" '
                f'type="button" role="option" aria-selected="{aria_selected}" '
                f'data-value="{escape(event["name"], quote=True)}" '
                f'data-event-id="{escape(event["id"], quote=True)}" '
                "data-event-document-types="
                f'"{escape(",".join(event["documentTypes"]), quote=True)}">'
                f"{escape(event['name'])}"
                "</button>"
            )
        )

    return (
        '<div class="custom-select" id="event-name-select">'
        '<input id="event-name" name="eventName" type="hidden" '
        f'value="{escape(selected_event["name"], quote=True)}" '
        f'data-event-id="{escape(selected_event["id"], quote=True)}" '
        "data-event-document-types="
        f'"{escape(",".join(selected_event["documentTypes"]), quote=True)}">'
        '<button class="custom-select-trigger" id="event-name-trigger" '
        'type="button" aria-expanded="false" aria-haspopup="listbox" '
        'aria-controls="event-name-options" '
        'aria-labelledby="event-name-label event-name-value">'
        '<span id="event-name-value" class="custom-select-value">'
        f"{escape(selected_event['name'])}"
        "</span>"
        '<span class="select-caret" aria-hidden="true"></span>'
        "</button>"
        '<div class="custom-select-menu" id="event-name-options" role="listbox" hidden>'
        f"{''.join(options_html)}"
        "</div>"
        "</div>"
    )


def build_home_document_type_options_html(
    copy: dict[str, str],
    selected_document_type: str,
    available_document_types: list[str] | None,
) -> str:
    options = [
        ("completionCert", "document_type_completion_cert"),
        ("taxReceipt", "document_type_tax_receipt"),
    ]
    options_html: list[str] = []

    for document_type, label_key in options:
        is_available = (
            available_document_types is None or document_type in available_document_types
        )
        is_selected = document_type == selected_document_type
        selected_class = " is-selected" if is_selected else ""
        aria_selected = "true" if is_selected else "false"
        hidden_attr = " hidden" if not is_available else ""
        options_html.append(
            (
                f'<button class="custom-select-option{selected_class}" '
                f'type="button" role="option" aria-selected="{aria_selected}"{hidden_attr} '
                f'data-value="{document_type}" data-label-key="{label_key}">'
                f"{escape(copy[label_key])}"
                "</button>"
            )
        )

    return "".join(options_html)


def resolve_home_document_type_label(document_type: str, copy: dict[str, str]) -> str:
    if document_type == "taxReceipt":
        return copy["document_type_tax_receipt"]

    return copy["document_type_completion_cert"]


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
    home_page_context = get_home_page_context(locale)
    context = {
        **home_page_context,
        **build_home_page_event_context(home_page_context),
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


@blueprint.function_name(name="public_events_list_api")
@blueprint.route(
    route="api/v1/events",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def public_events_list_api(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = build_public_events_json_payload()
    except EventStoreConfigurationError as exc:
        return build_home_api_error_response(
            503,
            "event_store_not_configured",
            str(exc),
        )
    except EventStoreOperationError as exc:
        return build_home_api_error_response(
            503,
            "event_store_unavailable",
            str(exc),
        )

    return build_home_api_json_response(payload)
