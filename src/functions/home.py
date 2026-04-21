from __future__ import annotations

import azure.functions as func

blueprint = func.Blueprint()


@blueprint.function_name(name="home_page")
@blueprint.route(
    route="{x:regex(^$)?}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def home_page(req: func.HttpRequest) -> func.HttpResponse:
    lines = [
        "iPlayground 完訓證明首頁",
        "",
        "用途: 供會眾生成或下載完訓證明",
        "status: 尚未串接實際功能",
    ]

    return func.HttpResponse(
        body="\n".join(lines),
        status_code=200,
        mimetype="text/plain",
        charset="utf-8",
    )
