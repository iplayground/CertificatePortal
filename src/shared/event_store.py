from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.shared.completion_metrics import (
    COMPLETION_METRIC_FIELDS,
    empty_completion_metrics,
    read_non_negative_counter,
)


EVENT_IDEMPOTENCY_NAMESPACE = "io.iplayground.ipg-certificate.admin.events"


class EventContainer(Protocol):
    def create_item(self, body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        raise NotImplementedError

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def query_items(
        self,
        query: str,
        *,
        enable_cross_partition_query: bool,
    ) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class EventStoreConfig:
    endpoint: str
    database_name: str
    container_name: str


class EventStoreConfigurationError(RuntimeError):
    pass


class EventStoreOperationError(RuntimeError):
    pass


def build_event_id(idempotency_key: str, *, actor: str) -> str:
    normalized_actor = actor.strip().lower() or "unknown"
    normalized_key = idempotency_key.strip()
    return f"evt_{uuid5(NAMESPACE_URL, f'{EVENT_IDEMPOTENCY_NAMESPACE}:{normalized_actor}:{normalized_key}')}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_event_document(
    *,
    actor: str,
    completion_hours: int | None,
    document_types: list[str],
    event_end_date: str,
    event_id: str,
    event_start_date: str,
    name: str,
    status: str,
    completion_cert_download_starts_at: str | None,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    return {
        "id": event_id,
        "name": name,
        "status": status,
        "documentTypes": document_types,
        "eventStartDate": event_start_date,
        "eventEndDate": event_end_date,
        "completionHours": completion_hours,
        "completionCertDownloadStartsAt": completion_cert_download_starts_at,
        "metrics": {"completionCert": empty_completion_metrics()},
        "createdAt": timestamp,
        "createdBy": actor,
        "updatedAt": timestamp,
        "updatedBy": actor,
    }


def create_event_document(
    *,
    container: EventContainer,
    event_document: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    try:
        return container.create_item(body=event_document), True
    except Exception as exc:
        if _is_cosmos_conflict_error(exc):
            event_id = str(event_document["id"])
            return container.read_item(item=event_id, partition_key=event_id), False
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError(
                "Cosmos DB 活動容器不存在。請確認 COSMOS_DATABASE_NAME 與 "
                "COSMOS_EVENTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def update_event_document(
    *,
    actor: str,
    completion_hours: int | None,
    completion_cert_download_starts_at: str | None,
    container: EventContainer,
    document_types: list[str],
    event_end_date: str,
    event_id: str,
    event_start_date: str,
    name: str,
    status: str,
) -> dict[str, Any]:
    try:
        existing_event = container.read_item(item=event_id, partition_key=event_id)
        updated_event = {
            **existing_event,
            "id": event_id,
            "name": name,
            "status": status,
            "documentTypes": document_types,
            "eventStartDate": event_start_date,
            "eventEndDate": event_end_date,
            "completionHours": completion_hours,
            "completionCertDownloadStartsAt": completion_cert_download_starts_at,
            "updatedAt": utc_now_iso(),
            "updatedBy": actor,
        }
        return container.replace_item(item=event_id, body=updated_event)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError("找不到要更新的活動。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器更新權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def read_event_completion_metrics(
    *,
    container: EventContainer,
    event_id: str,
) -> dict[str, int] | None:
    event = container.read_item(item=event_id, partition_key=event_id)
    return normalize_event_completion_metrics(event)


def normalize_event_completion_metrics(event: dict[str, Any]) -> dict[str, int] | None:
    metrics = event.get("metrics")
    if not isinstance(metrics, dict):
        return None

    completion_metrics = metrics.get("completionCert")
    if not isinstance(completion_metrics, dict):
        return None

    if any(field_name not in completion_metrics for field_name in COMPLETION_METRIC_FIELDS):
        return None

    if any(field_name not in COMPLETION_METRIC_FIELDS for field_name in completion_metrics):
        return None

    return {
        field_name: read_non_negative_counter(completion_metrics.get(field_name))
        for field_name in COMPLETION_METRIC_FIELDS
    }


def replace_event_completion_metrics(
    *,
    container: EventContainer,
    event_id: str,
    metrics: dict[str, int],
) -> dict[str, Any]:
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        updated_event = {
            **event,
            "metrics": {
                **(event.get("metrics") if isinstance(event.get("metrics"), dict) else {}),
                "completionCert": normalize_completion_metrics(metrics),
            },
            "metricsUpdatedAt": utc_now_iso(),
        }
        return container.replace_item(item=event_id, body=updated_event)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError("找不到要更新的活動。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器更新權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def increment_event_completion_metrics(
    *,
    container: EventContainer,
    deltas: dict[str, int],
    event_id: str,
) -> dict[str, Any]:
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        current_metrics = normalize_event_completion_metrics(event)
        metrics = current_metrics or empty_completion_metrics()
        for field_name, delta in deltas.items():
            if field_name not in COMPLETION_METRIC_FIELDS:
                continue
            metrics[field_name] = max(0, metrics[field_name] + delta)

        updated_event = {
            **event,
            "metrics": {
                **(event.get("metrics") if isinstance(event.get("metrics"), dict) else {}),
                "completionCert": metrics,
            },
            "metricsUpdatedAt": utc_now_iso(),
        }
        return container.replace_item(item=event_id, body=updated_event)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError("找不到要更新的活動。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器更新權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def normalize_completion_metrics(metrics: dict[str, int]) -> dict[str, int]:
    return {
        field_name: max(0, int(metrics.get(field_name, 0)))
        for field_name in COMPLETION_METRIC_FIELDS
    }


def list_event_documents(*, container: EventContainer) -> list[dict[str, Any]]:
    try:
        return list(
            container.query_items(
                query=(
                    "SELECT c.id, c.name, c.status, c.documentTypes, "
                    "c.eventStartDate, c.eventEndDate, c.completionHours, "
                    "c.completionCertDownloadStartsAt, c.metrics "
                    "FROM c ORDER BY c.createdAt DESC"
                ),
                enable_cross_partition_query=True,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError(
                "Cosmos DB 活動容器不存在。請確認 COSMOS_DATABASE_NAME 與 "
                "COSMOS_EVENTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise


def list_public_event_documents(*, container: EventContainer) -> list[dict[str, Any]]:
    try:
        return list(
            container.query_items(
                query=(
                    "SELECT c.id, c.name, c.documentTypes, "
                    "c.eventStartDate, c.eventEndDate, c.completionHours, "
                    "c.completionCertDownloadStartsAt FROM c "
                    "WHERE c.status = 'open' ORDER BY c.createdAt DESC"
                ),
                enable_cross_partition_query=True,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise EventStoreOperationError(
                "Cosmos DB 活動容器不存在。請確認 COSMOS_DATABASE_NAME 與 "
                "COSMOS_EVENTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise


def read_public_event_document(
    *,
    container: EventContainer,
    event_id: str,
) -> dict[str, Any] | None:
    try:
        return container.read_item(item=event_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            return None
        if _is_cosmos_forbidden_error(exc):
            raise EventStoreOperationError(
                "目前身分沒有 Cosmos DB 活動容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise


def get_event_store_config() -> EventStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    container_name = _read_env("COSMOS_EVENTS_CONTAINER")
    if not endpoint or not database_name or not container_name:
        raise EventStoreConfigurationError(
            "Cosmos DB 活動容器尚未設定完成。請設定 COSMOS_ENDPOINT、"
            "COSMOS_DATABASE_NAME 與 COSMOS_EVENTS_CONTAINER。"
        )

    return EventStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        container_name=container_name,
    )


@lru_cache(maxsize=1)
def get_events_container() -> EventContainer:
    config = get_event_store_config()
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise EventStoreConfigurationError(
            "缺少 Cosmos DB 套件。請安裝 azure-cosmos 與 azure-identity。"
        ) from exc

    client = CosmosClient(config.endpoint, credential=DefaultAzureCredential())
    database = client.get_database_client(config.database_name)
    return database.get_container_client(config.container_name)


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _is_cosmos_conflict_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 409


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 404


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 403
