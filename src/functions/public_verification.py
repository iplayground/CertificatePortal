from __future__ import annotations

import azure.functions as func

blueprint = func.Blueprint()


@blueprint.function_name(name="verify_cert_page")
@blueprint.route(
    route="verify/{certId}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def verify_cert_page(req: func.HttpRequest) -> func.HttpResponse:
    cert_id = req.route_params.get("certId", "")

    lines = [
        "iPlayground 完訓證明驗證頁面",
        "",
        f"certId: {cert_id}",
        "status: 尚未串接實際驗證資料",
    ]

    return func.HttpResponse(
        body="\n".join(lines),
        status_code=200,
        mimetype="text/plain",
        charset="utf-8",
    )
