from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass
from functools import lru_cache
from http.cookies import SimpleCookie
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

import azure.functions as func

from src.shared.portal_google_group_auth import (
    PortalGoogleGroupAuthorizationError,
    PORTAL_GOOGLE_GROUPS_READONLY_SCOPE,
    is_portal_google_group_authorization_configured,
    is_portal_google_user_in_allowed_group,
)

COOKIE_HEADER = "Cookie"
PORTAL_GOOGLE_LOGIN_PATH = "/portal/auth/google/login"
PORTAL_GOOGLE_CALLBACK_PATH = "/portal/auth/google/callback"
PORTAL_GOOGLE_LOGOUT_PATH = "/portal/auth/logout"
PORTAL_GOOGLE_STATE_COOKIE_NAME = "portal_google_oauth_state"
PORTAL_GOOGLE_SESSION_COOKIE_NAME = "portal_google_session"
GOOGLE_OIDC_DISCOVERY_DOCUMENT_URL = "https://accounts.google.com/.well-known/openid-configuration"
PORTAL_GOOGLE_OAUTH_SCOPES = (
    "openid",
    "email",
    "profile",
    PORTAL_GOOGLE_GROUPS_READONLY_SCOPE,
)
PORTAL_GOOGLE_STATE_MAX_AGE_SECONDS = 600
PORTAL_GOOGLE_SESSION_MAX_AGE_SECONDS = 28800
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortalPrincipal:
    is_authenticated: bool
    auth_type: str
    display_name: str
    email: str | None
    user_id: str | None


@dataclass(frozen=True)
class PortalAccess:
    principal: PortalPrincipal
    is_authorized: bool


@dataclass(frozen=True)
class PortalGoogleAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri_override: str | None


class PortalGoogleAuthError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 400, error_code: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


def build_portal_login_url(req: func.HttpRequest, post_login_redirect_uri: str) -> str:
    normalized_redirect_uri = _normalize_post_auth_redirect_uri(post_login_redirect_uri)
    return (
        f"{PORTAL_GOOGLE_LOGIN_PATH}"
        f"?post_login_redirect_uri={quote(normalized_redirect_uri, safe='/')}"
    )


def build_portal_logout_url(req: func.HttpRequest, post_logout_redirect_uri: str) -> str:
    normalized_redirect_uri = _normalize_post_auth_redirect_uri(post_logout_redirect_uri)
    return (
        f"{PORTAL_GOOGLE_LOGOUT_PATH}"
        f"?post_logout_redirect_uri={quote(normalized_redirect_uri, safe='/')}"
    )


def resolve_portal_access(req: func.HttpRequest) -> PortalAccess:
    principal = resolve_portal_principal(req)

    return PortalAccess(
        principal=principal,
        is_authorized=_is_portal_principal_authorized(principal),
    )


def resolve_portal_principal(req: func.HttpRequest) -> PortalPrincipal:
    portal_google_principal = _resolve_portal_google_principal(req)
    if portal_google_principal is not None:
        return portal_google_principal

    if is_portal_auth_bypass_enabled():
        bypass_email = _normalize_email(_read_env("PORTAL_AUTH_BYPASS_EMAIL", "local-admin@iplayground.io"))
        return PortalPrincipal(
            is_authenticated=True,
            auth_type="google-local-dev-bypass",
            display_name=_read_env("PORTAL_AUTH_BYPASS_DISPLAY_NAME", "本機管理者"),
            email=bypass_email,
            user_id="local-dev-bypass",
        )

    return PortalPrincipal(
        is_authenticated=False,
        auth_type="",
        display_name="",
        email=None,
        user_id=None,
    )


def is_portal_google_auth_configured() -> bool:
    return _get_portal_google_auth_config() is not None


def is_portal_google_group_auth_configured() -> bool:
    return is_portal_google_group_authorization_configured()


def build_portal_google_auth_start_response(req: func.HttpRequest) -> func.HttpResponse:
    config = _get_portal_google_auth_config_or_raise()
    post_login_redirect_uri = _normalize_post_auth_redirect_uri(req.params.get("post_login_redirect_uri", "/portal"))
    google_oidc_configuration = _load_google_oidc_configuration()
    authorization_endpoint = str(google_oidc_configuration.get("authorization_endpoint", "")).strip()
    if not authorization_endpoint:
        raise PortalGoogleAuthError("Google OIDC discovery document 未提供 authorization endpoint。", status_code=502)

    state_token = _sign_portal_google_token(
        {
            "exp": int(time.time()) + PORTAL_GOOGLE_STATE_MAX_AGE_SECONDS,
            "nonce": secrets.token_urlsafe(16),
            "post_login_redirect_uri": post_login_redirect_uri,
        },
        config.client_secret,
    )
    redirect_uri = _build_portal_google_redirect_uri(req, config)
    authorization_query = urlencode(
        {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(PORTAL_GOOGLE_OAUTH_SCOPES),
            "access_type": "online",
            "include_granted_scopes": "true",
            "prompt": "select_account",
            "state": state_token,
        }
    )
    location = f"{authorization_endpoint}?{authorization_query}"
    return _build_cookie_redirect_response(
        location=location,
        cookie_header=_build_set_cookie_header(
            PORTAL_GOOGLE_STATE_COOKIE_NAME,
            state_token,
            max_age=PORTAL_GOOGLE_STATE_MAX_AGE_SECONDS,
            req=req,
        ),
    )


def build_portal_google_auth_callback_response(req: func.HttpRequest) -> func.HttpResponse:
    config = _get_portal_google_auth_config_or_raise()
    oauth_error = req.params.get("error", "").strip()
    if oauth_error:
        raise PortalGoogleAuthError(oauth_error)

    authorization_code = req.params.get("code", "").strip()
    if not authorization_code:
        raise PortalGoogleAuthError("Google callback 缺少授權碼。")

    state_token = req.params.get("state", "").strip()
    if not state_token:
        raise PortalGoogleAuthError("Google callback 缺少 state。")

    expected_state_token = _get_cookie_value(req, PORTAL_GOOGLE_STATE_COOKIE_NAME)
    if not expected_state_token or not hmac.compare_digest(state_token, expected_state_token):
        raise PortalGoogleAuthError("Google callback state 驗證失敗。")

    state_payload = _verify_portal_google_token(state_token, config.client_secret)
    if state_payload is None:
        raise PortalGoogleAuthError("Google callback state 已失效或格式不正確。")

    redirect_uri = _build_portal_google_redirect_uri(req, config)
    token_payload = _exchange_portal_google_authorization_code(
        config=config,
        authorization_code=authorization_code,
        redirect_uri=redirect_uri,
    )
    granted_scopes = str(token_payload.get("scope", "")).split()
    LOGGER.info(
        "Google token scope grant result. scope_count=%d has_cloud_identity_group_scope=%s",
        len(granted_scopes),
        PORTAL_GOOGLE_GROUPS_READONLY_SCOPE in granted_scopes,
    )
    userinfo = _fetch_portal_google_userinfo(token_payload.get("access_token", ""))
    email = _normalize_email(str(userinfo.get("email", "")).strip())
    email_verified = bool(userinfo.get("email_verified"))
    if not email or not email_verified:
        raise PortalGoogleAuthError(
            "Google 回傳的使用者資訊缺少已驗證的 email。",
            status_code=403,
            error_code="google-login-data-authorization-required",
        )

    is_authorized = _authorize_portal_google_user(email, str(token_payload.get("access_token", "")).strip())
    if not is_authorized:
        raise PortalGoogleAuthError(
            "此 Google 帳號不在允許的管理群組內。",
            status_code=403,
            error_code="google-login-not-authorized",
        )

    display_name = str(userinfo.get("name", "")).strip() or email
    user_id = str(userinfo.get("sub", "")).strip() or None
    session_token = _sign_portal_google_token(
        {
            "exp": int(time.time()) + PORTAL_GOOGLE_SESSION_MAX_AGE_SECONDS,
            "email": email,
            "display_name": display_name,
            "user_id": user_id,
        },
        config.client_secret,
    )
    redirect_location = _normalize_post_auth_redirect_uri(
        str(state_payload.get("post_login_redirect_uri", "/portal"))
    )
    return _build_cookie_redirect_response(
        location=redirect_location,
        cookie_header=_build_set_cookie_header(
            PORTAL_GOOGLE_SESSION_COOKIE_NAME,
            session_token,
            max_age=PORTAL_GOOGLE_SESSION_MAX_AGE_SECONDS,
            req=req,
        ),
    )


def build_portal_google_logout_response(req: func.HttpRequest) -> func.HttpResponse:
    post_logout_redirect_uri = _normalize_post_auth_redirect_uri(req.params.get("post_logout_redirect_uri", "/portal"))
    return _build_cookie_redirect_response(
        location=post_logout_redirect_uri,
        cookie_header=_build_delete_cookie_header(PORTAL_GOOGLE_SESSION_COOKIE_NAME, req=req),
    )


def is_portal_auth_bypass_enabled() -> bool:
    enabled = _read_env("PORTAL_AUTH_BYPASS_ENABLED", "false").lower()
    return enabled in {"1", "true", "yes", "on"}


def _read_env(env_name: str, default_value: str) -> str:
    return os.getenv(env_name, default_value).strip()


def _authorize_portal_google_user(email: str, access_token: str) -> bool:
    try:
        return is_portal_google_user_in_allowed_group(email, access_token)
    except PortalGoogleGroupAuthorizationError as exc:
        raise PortalGoogleAuthError(
            str(exc),
            status_code=403,
            error_code="google-login-authorization-check-failed",
        ) from exc


def _is_portal_principal_authorized(principal: PortalPrincipal) -> bool:
    if not principal.is_authenticated:
        return False

    return principal.auth_type in {"google-oauth", "google-local-dev-bypass"}


def _resolve_portal_google_principal(req: func.HttpRequest) -> PortalPrincipal | None:
    config = _get_portal_google_auth_config()
    if config is None:
        return None

    session_token = _get_cookie_value(req, PORTAL_GOOGLE_SESSION_COOKIE_NAME)
    if not session_token:
        return None

    session_payload = _verify_portal_google_token(session_token, config.client_secret)
    if session_payload is None:
        return None

    email = _normalize_email(str(session_payload.get("email", "")).strip())
    if not email:
        return None

    display_name = str(session_payload.get("display_name", "")).strip() or email
    user_id = str(session_payload.get("user_id", "")).strip() or None
    return PortalPrincipal(
        is_authenticated=True,
        auth_type="google-oauth",
        display_name=display_name,
        email=email,
        user_id=user_id,
    )


def _get_portal_google_auth_config() -> PortalGoogleAuthConfig | None:
    client_id = _read_env("PORTAL_GOOGLE_CLIENT_ID", "")
    client_secret = _read_env("PORTAL_GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return None

    redirect_uri_override = _read_env("PORTAL_GOOGLE_REDIRECT_URI", "")
    return PortalGoogleAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri_override=redirect_uri_override or None,
    )


def _get_portal_google_auth_config_or_raise() -> PortalGoogleAuthConfig:
    config = _get_portal_google_auth_config()
    if config is not None:
        return config

    raise PortalGoogleAuthError(
        "Google 登入尚未設定完成。請設定 PORTAL_GOOGLE_CLIENT_ID 與 PORTAL_GOOGLE_CLIENT_SECRET。",
        status_code=500,
    )


@lru_cache(maxsize=1)
def _load_google_oidc_configuration() -> dict[str, Any]:
    return _perform_json_request(GOOGLE_OIDC_DISCOVERY_DOCUMENT_URL)


def _exchange_portal_google_authorization_code(
    *,
    config: PortalGoogleAuthConfig,
    authorization_code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    return _perform_json_request(
        "https://oauth2.googleapis.com/token",
        method="POST",
        data=urlencode(
            {
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": authorization_code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )


def _fetch_portal_google_userinfo(access_token: str) -> dict[str, Any]:
    if not access_token:
        raise PortalGoogleAuthError("Google token exchange 未取得 access token。", status_code=502)

    google_oidc_configuration = _load_google_oidc_configuration()
    userinfo_endpoint = str(google_oidc_configuration.get("userinfo_endpoint", "")).strip()
    if not userinfo_endpoint:
        raise PortalGoogleAuthError("Google OIDC discovery document 未提供 userinfo endpoint。", status_code=502)

    return _perform_json_request(
        userinfo_endpoint,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )


def _perform_json_request(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request = Request(url, data=data, method=method)
    for header_name, header_value in (headers or {}).items():
        request.add_header(header_name, header_value)

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_payload = exc.read().decode("utf-8", errors="ignore").strip()
        raise PortalGoogleAuthError(
            f"Google OAuth 請求失敗：HTTP {exc.code} {error_payload}",
            status_code=502,
        ) from exc
    except URLError as exc:
        raise PortalGoogleAuthError("無法連線到 Google OAuth 服務。", status_code=502) from exc
    except json.JSONDecodeError as exc:
        raise PortalGoogleAuthError("Google OAuth 回應不是合法 JSON。", status_code=502) from exc

    if not isinstance(payload, dict):
        raise PortalGoogleAuthError("Google OAuth 回應格式不正確。", status_code=502)

    return payload


def _build_portal_google_redirect_uri(req: func.HttpRequest, config: PortalGoogleAuthConfig) -> str:
    if config.redirect_uri_override:
        return config.redirect_uri_override

    return _build_absolute_url(req, PORTAL_GOOGLE_CALLBACK_PATH)


def _build_absolute_url(req: func.HttpRequest, path: str) -> str:
    request_url = urlsplit(req.url)
    scheme = _resolve_forwarded_value(req, "X-Forwarded-Proto") or request_url.scheme or "http"
    host = _resolve_forwarded_value(req, "X-Forwarded-Host") or request_url.netloc
    normalized_path = path if path.startswith("/") else f"/{path}"

    return urlunsplit((scheme, host, normalized_path, "", ""))


def _resolve_forwarded_value(req: func.HttpRequest, header_name: str) -> str | None:
    header_value = req.headers.get(header_name)
    if not header_value:
        return None

    first_value = header_value.split(",", maxsplit=1)[0].strip()
    return first_value or None


def _normalize_post_auth_redirect_uri(value: str | None) -> str:
    normalized_value = (value or "").strip()
    if not normalized_value.startswith("/") or normalized_value.startswith("//"):
        return "/portal"

    return normalized_value


def _build_cookie_redirect_response(*, location: str, cookie_header: str) -> func.HttpResponse:
    return func.HttpResponse(
        body="",
        status_code=302,
        headers={
            "Cache-Control": "no-store",
            "Location": location,
            "Set-Cookie": cookie_header,
        },
    )


def _build_set_cookie_header(
    cookie_name: str,
    cookie_value: str,
    *,
    max_age: int,
    req: func.HttpRequest,
) -> str:
    parts = [
        f"{cookie_name}={cookie_value}",
        "Path=/",
        f"Max-Age={max_age}",
        "HttpOnly",
        "SameSite=Lax",
    ]
    if _should_use_secure_cookies(req):
        parts.append("Secure")

    return "; ".join(parts)


def _build_delete_cookie_header(cookie_name: str, *, req: func.HttpRequest) -> str:
    return _build_set_cookie_header(cookie_name, "", max_age=0, req=req)


def _should_use_secure_cookies(req: func.HttpRequest) -> bool:
    request_url = urlsplit(req.url)
    scheme = _resolve_forwarded_value(req, "X-Forwarded-Proto") or request_url.scheme or ""
    return scheme.lower() == "https"


def _get_cookie_value(req: func.HttpRequest, cookie_name: str) -> str | None:
    raw_cookie_header = req.headers.get(COOKIE_HEADER, "")
    if not raw_cookie_header:
        return None

    parsed_cookies = SimpleCookie()
    parsed_cookies.load(raw_cookie_header)
    morsel = parsed_cookies.get(cookie_name)
    if morsel is None:
        return None

    cookie_value = morsel.value.strip()
    return cookie_value or None


def _sign_portal_google_token(payload: dict[str, Any], secret: str) -> str:
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def _verify_portal_google_token(token: str, secret: str) -> dict[str, Any] | None:
    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _base64url_decode(encoded_signature)
    if actual_signature is None or not hmac.compare_digest(actual_signature, expected_signature):
        return None

    payload_bytes = _base64url_decode(encoded_payload)
    if payload_bytes is None:
        return None

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None

    return payload


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _base64url_decode(value: str) -> bytes | None:
    padded_value = f"{value}{'=' * (-len(value) % 4)}"
    try:
        return base64.urlsafe_b64decode(padded_value.encode("utf-8"))
    except (ValueError, binascii.Error):
        return None


def _normalize_email(value: str | None) -> str | None:
    if value is None:
        return None

    normalized_value = value.strip().lower()
    if not normalized_value:
        return None

    return normalized_value
