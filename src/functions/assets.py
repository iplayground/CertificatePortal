from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import azure.functions as func

blueprint = func.Blueprint()

STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSET_DEFINITIONS: dict[str, tuple[Path, str, bool]] = {
    "favicon.png": (STATIC_DIR / "favicon.png", "image/png", False),
    "home.css": (STATIC_DIR / "home.css", "text/css", True),
    "home.js": (STATIC_DIR / "home.js", "application/javascript", True),
    "language_icon.svg": (STATIC_DIR / "language_icon.svg", "image/svg+xml", True),
    "logo_b_alpha.png": (STATIC_DIR / "logo_b_alpha.png", "image/png", False),
    "logo_sq_b.png": (STATIC_DIR / "logo_sq_b.png", "image/png", False),
    "google-g-icon.svg": (STATIC_DIR / "google-g-icon.svg", "image/svg+xml", True),
    "portal.css": (STATIC_DIR / "portal.css", "text/css", True),
    "portal-dashboard.js": (STATIC_DIR / "portal-dashboard.js", "application/javascript", True),
    "portal-dashboard-welcome.js": (
        STATIC_DIR / "portal-dashboard-welcome.js",
        "application/javascript",
        True,
    ),
    "portal-login.js": (STATIC_DIR / "portal-login.js", "application/javascript", True),
    "theme.css": (STATIC_DIR / "theme.css", "text/css", True),
}


@lru_cache(maxsize=None)
def load_asset_content(asset_name: str) -> bytes:
    asset_path, _, is_text = ASSET_DEFINITIONS[asset_name]
    if is_text:
        return asset_path.read_text(encoding="utf-8").encode("utf-8")
    return asset_path.read_bytes()


@blueprint.function_name(name="static_asset")
@blueprint.route(
    route="assets/{asset_name}",
    methods=["GET"],
    auth_level=func.AuthLevel.ANONYMOUS,
)
def static_asset(req: func.HttpRequest) -> func.HttpResponse:
    asset_name = req.route_params.get("asset_name", "")
    asset_definition = ASSET_DEFINITIONS.get(asset_name)

    if asset_definition is None:
        return func.HttpResponse(
            body="Asset not found",
            status_code=404,
            mimetype="text/plain",
            charset="utf-8",
        )

    _, mimetype, is_text = asset_definition

    return func.HttpResponse(
        body=load_asset_content(asset_name),
        status_code=200,
        mimetype=mimetype,
        charset="utf-8" if is_text else None,
    )
