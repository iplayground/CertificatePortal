from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from pathlib import Path
import re

import azure.functions as func

blueprint = func.Blueprint()

STATIC_DIR = Path(__file__).resolve().parent / "static"
ASSET_DEFINITIONS: dict[str, tuple[Path, str, bool]] = {
    "favicon.png": (STATIC_DIR / "favicon.png", "image/png", False),
    "home.css": (STATIC_DIR / "home.css", "text/css", True),
    "home.js": (STATIC_DIR / "home.js", "application/javascript", True),
    "language_icon.svg": (STATIC_DIR / "language_icon.svg", "image/svg+xml", True),
    "locale-switcher.js": (
        STATIC_DIR / "locale-switcher.js",
        "application/javascript",
        True,
    ),
    "logo_b_alpha.png": (STATIC_DIR / "logo_b_alpha.png", "image/png", False),
    "logo_sq_b.png": (STATIC_DIR / "logo_sq_b.png", "image/png", False),
    "page-alert.js": (STATIC_DIR / "page-alert.js", "application/javascript", True),
    "google-g-icon.svg": (STATIC_DIR / "google-g-icon.svg", "image/svg+xml", True),
    "portal.css": (STATIC_DIR / "portal.css", "text/css", True),
    "portal-datetime-picker.js": (
        STATIC_DIR / "portal-datetime-picker.js",
        "application/javascript",
        True,
    ),
    "portal-event-cache.js": (
        STATIC_DIR / "portal-event-cache.js",
        "application/javascript",
        True,
    ),
    "portal-dashboard-completion-certs.js": (
        STATIC_DIR / "portal-dashboard-completion-certs.js",
        "application/javascript",
        True,
    ),
    "portal-dashboard-completion-reviews.js": (
        STATIC_DIR / "portal-dashboard-completion-reviews.js",
        "application/javascript",
        True,
    ),
    "portal-dashboard-events.js": (
        STATIC_DIR / "portal-dashboard-events.js",
        "application/javascript",
        True,
    ),
    "portal-dashboard-tax-receipts.js": (
        STATIC_DIR / "portal-dashboard-tax-receipts.js",
        "application/javascript",
        True,
    ),
    "portal-dashboard.js": (STATIC_DIR / "portal-dashboard.js", "application/javascript", True),
    "portal-dashboard-welcome.js": (
        STATIC_DIR / "portal-dashboard-welcome.js",
        "application/javascript",
        True,
    ),
    "portal-login.js": (STATIC_DIR / "portal-login.js", "application/javascript", True),
    "tax-receipt-generated-at-help.png": (
        STATIC_DIR / "tax-receipt-generated-at-help.png",
        "image/png",
        False,
    ),
    "theme.css": (STATIC_DIR / "theme.css", "text/css", True),
    "verify.css": (STATIC_DIR / "verify.css", "text/css", True),
    "verify.js": (STATIC_DIR / "verify.js", "application/javascript", True),
}
ASSET_REFERENCE_PATTERN = re.compile(
    r"(?P<prefix>['\"])/assets/(?P<asset_name>[^?'\"#)]+)(?P<suffix>['\"])"
)
VERSIONED_ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"
UNVERSIONED_ASSET_CACHE_CONTROL = "no-store"


@lru_cache(maxsize=None)
def load_raw_asset_content(asset_name: str) -> bytes:
    asset_path, _, is_text = ASSET_DEFINITIONS[asset_name]
    if is_text:
        return asset_path.read_text(encoding="utf-8").encode("utf-8")
    return asset_path.read_bytes()


@lru_cache(maxsize=None)
def load_asset_content(asset_name: str) -> bytes:
    asset_path, _, is_text = ASSET_DEFINITIONS[asset_name]
    if not is_text:
        return load_raw_asset_content(asset_name)

    content = asset_path.read_text(encoding="utf-8")
    return rewrite_asset_references(content).encode("utf-8")


def rewrite_asset_references(content: str) -> str:
    def replace_reference(match: re.Match[str]) -> str:
        asset_name = match.group("asset_name")
        if asset_name not in ASSET_DEFINITIONS:
            return match.group(0)

        return f"{match.group('prefix')}{asset_url(asset_name)}{match.group('suffix')}"

    return ASSET_REFERENCE_PATTERN.sub(replace_reference, content)


@lru_cache(maxsize=None)
def asset_version(asset_name: str) -> str:
    return sha256(load_asset_content(asset_name)).hexdigest()[:16]


def asset_url(asset_name: str) -> str:
    if asset_name not in ASSET_DEFINITIONS:
        raise KeyError(asset_name)

    return f"/assets/{asset_name}?v={asset_version(asset_name)}"


def build_asset_url_context(*asset_names: str) -> dict[str, str]:
    return {
        f"asset_{asset_name.replace('-', '_').replace('.', '_')}_url": asset_url(asset_name)
        for asset_name in asset_names
    }


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
    content = load_asset_content(asset_name)
    etag = f'"{asset_version(asset_name)}"'
    request_version = req.params.get("v", "").strip()
    cache_control = (
        VERSIONED_ASSET_CACHE_CONTROL
        if request_version == asset_version(asset_name)
        else UNVERSIONED_ASSET_CACHE_CONTROL
    )

    if req.headers.get("If-None-Match") == etag:
        return func.HttpResponse(
            body=b"",
            status_code=304,
            headers={
                "Cache-Control": cache_control,
                "ETag": etag,
            },
        )

    return func.HttpResponse(
        body=content,
        status_code=200,
        mimetype=mimetype,
        charset="utf-8" if is_text else None,
        headers={
            "Cache-Control": cache_control,
            "ETag": etag,
            "X-Content-Type-Options": "nosniff",
        },
    )
