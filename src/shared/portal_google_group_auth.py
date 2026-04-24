from __future__ import annotations

import json
import hashlib
import logging
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PORTAL_GOOGLE_GROUPS_READONLY_SCOPE = "https://www.googleapis.com/auth/cloud-identity.groups.readonly"
PORTAL_GOOGLE_GROUP_LOOKUP_URL = "https://cloudidentity.googleapis.com/v1/groups:lookup"
PORTAL_GOOGLE_GROUP_MEMBERSHIP_LOOKUP_URL_TEMPLATE = "https://cloudidentity.googleapis.com/v1/{group_name}/memberships:lookup"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PortalGoogleGroupAuthorizationConfig:
    allowed_group_keys: tuple[str, ...]


class PortalGoogleGroupAuthorizationError(RuntimeError):
    pass


def is_portal_google_group_authorization_configured() -> bool:
    return _get_portal_google_group_authorization_config() is not None


def get_portal_google_allowed_group_keys(email: str | None = None) -> tuple[str, ...]:
    config = _get_portal_google_group_authorization_config()
    if config is None:
        return ()

    return _resolve_portal_google_allowed_group_keys(config.allowed_group_keys, email)


def is_portal_google_user_in_allowed_group(email: str, access_token: str) -> bool:
    config = _get_portal_google_group_authorization_config()
    if config is None:
        raise PortalGoogleGroupAuthorizationError(
            "Google 群組授權尚未設定完成。請設定 PORTAL_GOOGLE_ALLOWED_GROUP_KEYS。"
        )
    if not access_token.strip():
        raise PortalGoogleGroupAuthorizationError("Google token exchange 未取得足以檢查群組授權的 access token。")

    allowed_group_keys = _resolve_portal_google_allowed_group_keys(config.allowed_group_keys, email)
    completed_lookup_count = 0
    lookup_errors: list[PortalGoogleGroupAuthorizationError] = []
    for group_key in allowed_group_keys:
        try:
            is_member = _is_portal_google_user_in_group(
                email=email,
                group_key=group_key,
                access_token=access_token,
            )
        except PortalGoogleGroupAuthorizationError as exc:
            lookup_errors.append(exc)
            LOGGER.info(
                "Google per-group membership lookup unavailable. group_fingerprint=%s error=%s",
                _fingerprint_portal_google_group_key(group_key),
                _summarize_portal_google_group_authorization_error(exc),
            )
            continue

        completed_lookup_count += 1
        LOGGER.info(
            "Google per-group membership lookup result. group_fingerprint=%s matched=%s",
            _fingerprint_portal_google_group_key(group_key),
            is_member,
        )
        if is_member:
            return True

    if completed_lookup_count == 0 and lookup_errors:
        raise PortalGoogleGroupAuthorizationError("Google 群組授權檢查未完成，所有允許群組查詢皆失敗。") from lookup_errors[0]

    return False


def _is_portal_google_user_in_group(
    *,
    email: str,
    group_key: str,
    access_token: str,
) -> bool:
    group_name = _lookup_portal_google_group_name(group_key, access_token)
    membership_name = _lookup_portal_google_membership_name(
        group_name=group_name,
        email=email,
        access_token=access_token,
    )
    return membership_name is not None


def _lookup_portal_google_group_name(group_key: str, access_token: str) -> str:
    payload = _perform_portal_google_groups_json_request(
        _build_url_with_query(
            PORTAL_GOOGLE_GROUP_LOOKUP_URL,
            {
                "groupKey.id": group_key,
            },
        ),
        access_token=access_token,
        not_found_message="找不到指定的 Google 群組，或目前登入的 Google 帳號無法查看該群組。",
        forbidden_message=(
            "Google 群組授權請求被拒絕。請確認 Google OAuth scopes 已包含 "
            "cloud-identity.groups.readonly，且目標群組對組織使用者可見。"
        ),
        service_label="Cloud Identity Groups API",
    )
    group_name = str(payload.get("name", "")).strip()
    if not group_name.startswith("groups/"):
        raise PortalGoogleGroupAuthorizationError("Cloud Identity Groups API 未回傳合法的群組資源名稱。")

    return group_name


def _lookup_portal_google_membership_name(
    *,
    group_name: str,
    email: str,
    access_token: str,
) -> str | None:
    payload = _perform_portal_google_groups_json_request(
        _build_url_with_query(
            PORTAL_GOOGLE_GROUP_MEMBERSHIP_LOOKUP_URL_TEMPLATE.format(group_name=group_name),
            {
                "memberKey.id": email,
            },
        ),
        access_token=access_token,
        not_found_message=None,
        forbidden_message=(
            "Google 群組授權請求被拒絕。請確認目標群組的成員名單可供組織內使用者查看。"
        ),
        service_label="Cloud Identity Groups API",
    )
    if payload is None:
        return None

    membership_name = str(payload.get("name", "")).strip()
    if not membership_name.startswith(f"{group_name}/memberships/"):
        raise PortalGoogleGroupAuthorizationError("Cloud Identity Groups API 未回傳合法的 membership 資源名稱。")

    return membership_name


def _get_portal_google_group_authorization_config() -> PortalGoogleGroupAuthorizationConfig | None:
    allowed_group_keys = _read_portal_google_allowed_group_keys()
    if not allowed_group_keys:
        return None

    return PortalGoogleGroupAuthorizationConfig(
        allowed_group_keys=allowed_group_keys,
    )


def _read_portal_google_allowed_group_keys() -> tuple[str, ...]:
    configured_value = _read_env("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "")
    if not configured_value:
        return ()

    normalized_tokens = configured_value.replace("\r", "\n").replace(";", ",").replace("\n", ",").split(",")
    normalized_group_keys = [_normalize_portal_google_group_key(token.strip()) for token in normalized_tokens if token.strip()]
    return tuple(dict.fromkeys(normalized_group_keys))


def _resolve_portal_google_allowed_group_keys(
    allowed_group_keys: tuple[str, ...],
    email: str | None,
) -> tuple[str, ...]:
    return tuple(_expand_portal_google_group_key(group_key, email) for group_key in allowed_group_keys)


def _normalize_portal_google_group_key(group_key: str) -> str:
    return group_key.strip().lower()


def _fingerprint_portal_google_group_key(group_key: str) -> str:
    normalized_group_key = _normalize_portal_google_group_key(group_key)
    if not normalized_group_key:
        return ""

    return hashlib.sha256(normalized_group_key.encode("utf-8")).hexdigest()[:12]


def _summarize_portal_google_group_authorization_error(
    exc: PortalGoogleGroupAuthorizationError,
) -> str:
    message = str(exc)
    if "HTTP " in message:
        return message.split("{", 1)[0].strip()

    return exc.__class__.__name__


def _expand_portal_google_group_key(group_key: str, email: str | None) -> str:
    if not group_key or "@" in group_key:
        return group_key

    email_domain = _extract_email_domain(email)
    if email_domain is None:
        return group_key

    return f"{group_key}@{email_domain}"


def _extract_email_domain(email: str | None) -> str | None:
    if not isinstance(email, str):
        return None

    local_part, separator, domain = email.strip().lower().partition("@")
    if not separator or not local_part or not domain:
        return None

    return domain


def _build_url_with_query(base_url: str, query_params: dict[str, str]) -> str:
    return f"{base_url}?{urlencode(query_params)}"


def _perform_portal_google_groups_json_request(
    url: str,
    *,
    access_token: str,
    not_found_message: str | None,
    forbidden_message: str,
    service_label: str,
) -> dict[str, object] | None:
    if not access_token.strip():
        raise PortalGoogleGroupAuthorizationError("Google token exchange 未取得足以檢查群組授權的 access token。")

    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    try:
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        error_payload = exc.read().decode("utf-8", errors="ignore").strip()
        error_summary = _summarize_portal_google_api_error_payload(error_payload)
        if exc.code in {401, 403}:
            raise PortalGoogleGroupAuthorizationError(f"{forbidden_message} HTTP {exc.code}{error_summary}") from exc
        if exc.code == 404 and not_found_message is None:
            return None
        if exc.code == 404:
            raise PortalGoogleGroupAuthorizationError(f"{not_found_message} HTTP {exc.code}{error_summary}") from exc

        raise PortalGoogleGroupAuthorizationError(
            f"{service_label} 請求失敗：HTTP {exc.code}{error_summary}"
        ) from exc
    except URLError as exc:
        raise PortalGoogleGroupAuthorizationError(f"無法連線到 {service_label}。") from exc
    except json.JSONDecodeError as exc:
        raise PortalGoogleGroupAuthorizationError(f"{service_label} 回應不是合法 JSON。") from exc

    if not isinstance(payload, dict):
        raise PortalGoogleGroupAuthorizationError(f"{service_label} 回應格式不正確。")

    return payload


def _summarize_portal_google_api_error_payload(error_payload: str) -> str:
    if not error_payload:
        return ""

    try:
        parsed_payload = json.loads(error_payload)
    except json.JSONDecodeError:
        return ""

    if not isinstance(parsed_payload, dict):
        return ""

    error = parsed_payload.get("error", {})
    if not isinstance(error, dict):
        return ""

    parts: list[str] = []
    status = str(error.get("status", "")).strip()
    if status:
        parts.append(f"status={status}")

    details = error.get("details", [])
    if isinstance(details, list):
        for detail in details:
            if not isinstance(detail, dict):
                continue
            reason = str(detail.get("reason", "")).strip()
            if reason:
                parts.append(f"reason={reason}")
            domain = str(detail.get("domain", "")).strip()
            if domain:
                parts.append(f"domain={domain}")
            metadata = detail.get("metadata", {})
            if isinstance(metadata, dict):
                service = str(metadata.get("service", "")).strip()
                if service:
                    parts.append(f"service={service}")

    errors = error.get("errors", [])
    if isinstance(errors, list):
        for error_item in errors:
            if not isinstance(error_item, dict):
                continue
            reason = str(error_item.get("reason", "")).strip()
            if reason:
                parts.append(f"reason={reason}")

    unique_parts = tuple(dict.fromkeys(parts))
    if not unique_parts:
        return ""

    return f" ({', '.join(unique_parts)})"


def _read_env(env_name: str, default_value: str) -> str:
    return os.getenv(env_name, default_value).strip()
