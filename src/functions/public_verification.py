from __future__ import annotations

import azure.functions as func

from src.shared.i18n import get_verify_page_copy, localized_response_headers, resolve_locale

blueprint = func.Blueprint()


@blueprint.function_name(name="verify_cert_page")
@blueprint.route(
    route="verify/{certId}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def verify_cert_page(req: func.HttpRequest) -> func.HttpResponse:
    locale = resolve_locale(req)
    copy = get_verify_page_copy(locale)
    cert_id = req.route_params.get("certId", "")

    lines = [
        copy["title"],
        "",
        f'{copy["cert_id_label"]}: {cert_id}',
        f'{copy["status_label"]}: {copy["status_value"]}',
    ]

    return func.HttpResponse(
        body="\n".join(lines),
        status_code=200,
        mimetype="text/plain",
        charset="utf-8",
        headers=localized_response_headers(locale),
    )
