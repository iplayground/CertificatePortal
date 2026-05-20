from __future__ import annotations

import os
from threading import Lock
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.shared.cosmos_options import build_public_lookup_cosmos_timeout_options
from src.shared.event_store import utc_now_iso


PUBLIC_LOOKUP_FAILURE_LIMIT = 5
PUBLIC_LOOKUP_FAILURE_WINDOW_HOURS = 24
PUBLIC_LOOKUP_BLOCK_HOURS = 24
PUBLIC_LOOKUP_NOT_AVAILABLE_LIMIT = 10
PUBLIC_LOOKUP_NOT_AVAILABLE_WINDOW_HOURS = 24
PUBLIC_LOOKUP_NOT_AVAILABLE_BLOCK_HOURS = 12
PUBLIC_LOOKUP_LOCAL_BLOCK_CACHE_HOURS = 1
PUBLIC_LOOKUP_ATTEMPT_NAMESPACE = "io.iplayground.ipg-certificate.public-lookups"
_PUBLIC_LOOKUP_BLOCK_CACHE: dict[str, datetime] = {}
_PUBLIC_LOOKUP_ATTEMPT_CACHE: dict[str, tuple[dict[str, Any], datetime]] = {}
_PUBLIC_LOOKUP_BLOCK_CACHE_LOCK = Lock()


class PublicLookupContainer(Protocol):
    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class PublicLookupStoreConfig:
    endpoint: str
    database_name: str
    lookup_attempts_container_name: str


class PublicLookupStoreConfigurationError(RuntimeError):
    pass


class PublicLookupStoreOperationError(RuntimeError):
    pass


def build_public_lookup_attempt_id(ip_address: str) -> str:
    normalized_ip = ip_address.strip().lower()
    namespace_value = f"{PUBLIC_LOOKUP_ATTEMPT_NAMESPACE}:{normalized_ip}"
    return f"lookup_{uuid5(NAMESPACE_URL, namespace_value)}"


def read_public_lookup_attempt_document(
    *,
    attempt_id: str,
    container: PublicLookupContainer,
) -> dict[str, Any] | None:
    try:
        document = container.read_item(
            item=attempt_id,
            partition_key=attempt_id,
            **build_public_lookup_cosmos_timeout_options(),
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            return None
        if _is_cosmos_forbidden_error(exc):
            raise PublicLookupStoreOperationError(
                "目前身分沒有 Cosmos DB 公開查詢限制容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise PublicLookupStoreOperationError("公開查詢限制資料讀取暫時失敗。") from exc

    if not isinstance(document, dict):
        raise PublicLookupStoreOperationError("公開查詢限制資料格式不合法。")

    return document


def is_public_lookup_blocked(
    *,
    attempt_document: dict[str, Any] | None,
    now: str | None = None,
) -> bool:
    if not attempt_document:
        return False

    blocked_until = _parse_utc_iso(str(attempt_document.get("blockedUntil", "")))
    if blocked_until is None:
        return False

    current_time = _parse_utc_iso(now or utc_now_iso())
    return current_time is not None and blocked_until > current_time


def is_public_lookup_blocked_by_local_cache(
    *,
    attempt_id: str,
    now: str | None = None,
) -> bool:
    current_time = _parse_utc_iso(now or utc_now_iso())
    if current_time is None:
        return False

    with _PUBLIC_LOOKUP_BLOCK_CACHE_LOCK:
        blocked_until = _PUBLIC_LOOKUP_BLOCK_CACHE.get(attempt_id)
        if blocked_until is None:
            return False

        if blocked_until <= current_time:
            _PUBLIC_LOOKUP_BLOCK_CACHE.pop(attempt_id, None)
            return False

        return True


def read_public_lookup_cached_attempt_document(
    *,
    attempt_id: str,
    now: str | None = None,
) -> dict[str, Any] | None:
    current_time = _parse_utc_iso(now or utc_now_iso())
    if current_time is None:
        return None

    with _PUBLIC_LOOKUP_BLOCK_CACHE_LOCK:
        cached_value = _PUBLIC_LOOKUP_ATTEMPT_CACHE.get(attempt_id)
        if cached_value is None:
            return None

        attempt_document, expires_at = cached_value
        if expires_at <= current_time:
            _PUBLIC_LOOKUP_ATTEMPT_CACHE.pop(attempt_id, None)
            return None

        return dict(attempt_document)


def remember_public_lookup_attempt_document(
    *,
    attempt_id: str,
    attempt_document: dict[str, Any],
    now: str | None = None,
) -> None:
    current_time = _parse_utc_iso(now or utc_now_iso())
    if current_time is None:
        return

    expires_at = current_time + timedelta(hours=PUBLIC_LOOKUP_LOCAL_BLOCK_CACHE_HOURS)
    with _PUBLIC_LOOKUP_BLOCK_CACHE_LOCK:
        _PUBLIC_LOOKUP_ATTEMPT_CACHE[attempt_id] = (dict(attempt_document), expires_at)


def remember_public_lookup_block(
    *,
    attempt_id: str,
    attempt_document: dict[str, Any],
    now: str | None = None,
) -> None:
    blocked_until = _parse_utc_iso(str(attempt_document.get("blockedUntil", "")))
    if blocked_until is None:
        return

    current_time = _parse_utc_iso(now or utc_now_iso())
    if current_time is None:
        return

    local_cache_until = min(
        blocked_until,
        current_time + timedelta(hours=PUBLIC_LOOKUP_LOCAL_BLOCK_CACHE_HOURS),
    )
    if local_cache_until <= current_time:
        return

    with _PUBLIC_LOOKUP_BLOCK_CACHE_LOCK:
        _PUBLIC_LOOKUP_BLOCK_CACHE[attempt_id] = local_cache_until


def clear_public_lookup_local_block(*, attempt_id: str) -> None:
    with _PUBLIC_LOOKUP_BLOCK_CACHE_LOCK:
        _PUBLIC_LOOKUP_BLOCK_CACHE.pop(attempt_id, None)
        _PUBLIC_LOOKUP_ATTEMPT_CACHE.pop(attempt_id, None)


def record_public_lookup_failure(
    *,
    attempt_id: str,
    container: PublicLookupContainer,
    existing_document: dict[str, Any] | None,
    ip_address: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    timestamp_value = _parse_utc_iso(timestamp)
    if timestamp_value is None:
        raise ValueError("now must use UTC ISO 8601 format.")
    first_failed_at = _parse_utc_iso(
        str((existing_document or {}).get("firstFailedAt", ""))
    )
    previous_failure_count = int((existing_document or {}).get("failureCount") or 0)
    in_failure_window = (
        first_failed_at is not None
        and timestamp_value - first_failed_at < timedelta(hours=PUBLIC_LOOKUP_FAILURE_WINDOW_HOURS)
    )

    if in_failure_window:
        failure_count = previous_failure_count + 1
        next_first_failed_at = first_failed_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        failure_count = 1
        next_first_failed_at = timestamp

    blocked_until = None
    if failure_count >= PUBLIC_LOOKUP_FAILURE_LIMIT:
        blocked_until = (
            timestamp_value + timedelta(hours=PUBLIC_LOOKUP_BLOCK_HOURS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing_document = existing_document or {}
    document = {
        "id": attempt_id,
        "ipAddress": ip_address,
        "failureCount": failure_count,
        "firstFailedAt": next_first_failed_at,
        "lastFailedAt": timestamp,
        "notAvailableCount": int(existing_document.get("notAvailableCount") or 0),
        "firstNotAvailableAt": existing_document.get("firstNotAvailableAt"),
        "lastNotAvailableAt": existing_document.get("lastNotAvailableAt"),
        "blockedUntil": blocked_until,
        "updatedAt": timestamp,
    }

    try:
        return container.upsert_item(
            body=document,
            **build_public_lookup_cosmos_timeout_options(),
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise PublicLookupStoreOperationError(
                "Cosmos DB 公開查詢限制容器不存在。請確認 "
                "COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise PublicLookupStoreOperationError(
                "目前身分沒有 Cosmos DB 公開查詢限制容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise PublicLookupStoreOperationError("公開查詢限制資料寫入暫時失敗。") from exc


def record_public_lookup_not_available(
    *,
    attempt_id: str,
    container: PublicLookupContainer,
    existing_document: dict[str, Any] | None,
    ip_address: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    timestamp_value = _parse_utc_iso(timestamp)
    if timestamp_value is None:
        raise ValueError("now must use UTC ISO 8601 format.")

    existing_document = existing_document or {}
    first_not_available_at = _parse_utc_iso(
        str(existing_document.get("firstNotAvailableAt", ""))
    )
    previous_not_available_count = int(
        existing_document.get("notAvailableCount") or 0
    )
    in_not_available_window = (
        first_not_available_at is not None
        and timestamp_value - first_not_available_at
        < timedelta(hours=PUBLIC_LOOKUP_NOT_AVAILABLE_WINDOW_HOURS)
    )

    if in_not_available_window:
        not_available_count = previous_not_available_count + 1
        next_first_not_available_at = first_not_available_at.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    else:
        not_available_count = 1
        next_first_not_available_at = timestamp

    blocked_until = None
    if not_available_count >= PUBLIC_LOOKUP_NOT_AVAILABLE_LIMIT:
        blocked_until = (
            timestamp_value + timedelta(hours=PUBLIC_LOOKUP_NOT_AVAILABLE_BLOCK_HOURS)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    document = {
        "id": attempt_id,
        "ipAddress": ip_address,
        "failureCount": int(existing_document.get("failureCount") or 0),
        "firstFailedAt": existing_document.get("firstFailedAt"),
        "lastFailedAt": existing_document.get("lastFailedAt"),
        "notAvailableCount": not_available_count,
        "firstNotAvailableAt": next_first_not_available_at,
        "lastNotAvailableAt": timestamp,
        "blockedUntil": blocked_until,
        "updatedAt": timestamp,
    }

    try:
        return container.upsert_item(
            body=document,
            **build_public_lookup_cosmos_timeout_options(),
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise PublicLookupStoreOperationError(
                "Cosmos DB 公開查詢限制容器不存在。請確認 "
                "COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise PublicLookupStoreOperationError(
                "目前身分沒有 Cosmos DB 公開查詢限制容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise PublicLookupStoreOperationError("公開查詢限制資料寫入暫時失敗。") from exc


def record_public_lookup_success(
    *,
    attempt_id: str,
    container: PublicLookupContainer,
    ip_address: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    document = {
        "id": attempt_id,
        "ipAddress": ip_address,
        "failureCount": 0,
        "firstFailedAt": None,
        "lastFailedAt": None,
        "notAvailableCount": 0,
        "firstNotAvailableAt": None,
        "lastNotAvailableAt": None,
        "blockedUntil": None,
        "updatedAt": timestamp,
    }

    try:
        return container.upsert_item(
            body=document,
            **build_public_lookup_cosmos_timeout_options(),
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise PublicLookupStoreOperationError(
                "Cosmos DB 公開查詢限制容器不存在。請確認 "
                "COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise PublicLookupStoreOperationError(
                "目前身分沒有 Cosmos DB 公開查詢限制容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise PublicLookupStoreOperationError("公開查詢限制資料寫入暫時失敗。") from exc


def get_public_lookup_store_config() -> PublicLookupStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    lookup_attempts_container_name = _read_env("COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER")
    if not endpoint or not database_name or not lookup_attempts_container_name:
        raise PublicLookupStoreConfigurationError(
            "Cosmos DB 公開查詢限制容器尚未設定完成。請設定 COSMOS_ENDPOINT、"
            "COSMOS_DATABASE_NAME 與 COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER。"
        )

    return PublicLookupStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        lookup_attempts_container_name=lookup_attempts_container_name,
    )


@lru_cache(maxsize=1)
def get_public_lookup_attempts_container() -> PublicLookupContainer:
    config = get_public_lookup_store_config()
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise PublicLookupStoreConfigurationError(
            "缺少 Cosmos DB 套件。請安裝 azure-cosmos 與 azure-identity。"
        ) from exc

    client = CosmosClient(config.endpoint, credential=DefaultAzureCredential())
    database = client.get_database_client(config.database_name)
    return database.get_container_client(config.lookup_attempts_container_name)


def _parse_utc_iso(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 404


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 403
