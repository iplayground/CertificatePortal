from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.shared.event_store import utc_now_iso


VOLUNTEER_SERVICE_CERT_NAMESPACE = (
    "io.iplayground.ipg-certificate.volunteer-service-certs"
)


class VolunteerServiceContainer(Protocol):
    def create_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def replace_item(self, item: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class VolunteerServiceStoreConfig:
    endpoint: str
    database_name: str
    container_name: str


class VolunteerServiceStoreConfigurationError(RuntimeError):
    pass


class VolunteerServiceStoreOperationError(RuntimeError):
    pass


def build_volunteer_service_cert_id(
    *,
    completion_cert_id: str,
    event_id: str,
) -> str:
    normalized_event_id = event_id.strip()
    normalized_completion_cert_id = completion_cert_id.strip()
    namespace_value = (
        f"{VOLUNTEER_SERVICE_CERT_NAMESPACE}:"
        f"{normalized_event_id}:{normalized_completion_cert_id}"
    )
    return f"vscert_{uuid5(NAMESPACE_URL, namespace_value)}"


def build_volunteer_service_cert_document(
    *,
    actor: str,
    completion_cert: dict[str, Any],
    event: dict[str, Any] | None = None,
    volunteer_service_cert_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    event_data = event if isinstance(event, dict) else {}
    return {
        "id": volunteer_service_cert_id,
        "eventId": str(completion_cert.get("eventId", "")).strip(),
        "sourceCompletionCertId": str(completion_cert.get("id", "")).strip(),
        "number": completion_cert.get("number"),
        "kktixId": str(completion_cert.get("kktixId", "")).strip(),
        "badgeName": str(completion_cert.get("badgeName", "")).strip(),
        "name": str(completion_cert.get("name", "")).strip(),
        "email": str(completion_cert.get("email", "")).strip(),
        "serviceOrganization": str(completion_cert.get("organization", "")).strip(),
        "serviceHours": normalize_optional_int(event_data.get("completionHours")),
        "serviceStartDate": normalize_optional_string(event_data.get("eventStartDate")),
        "serviceEndDate": normalize_optional_string(event_data.get("eventEndDate")),
        "downloadEnabled": str(completion_cert.get("attendanceStatus", "")).strip()
        == "checkedIn",
        "certStatus": "notIssued",
        "sourceCreatedAt": completion_cert.get("createdAt"),
        "createdAt": timestamp,
        "createdBy": actor,
        "updatedAt": timestamp,
        "updatedBy": actor,
    }


def normalize_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    normalized_value = str(value).strip()
    return normalized_value or None


def normalize_optional_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, str):
        normalized_value = value.strip()
        if normalized_value.isdigit():
            return int(normalized_value)
    return None


def create_volunteer_service_cert_document(
    *,
    container: VolunteerServiceContainer,
    document: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    try:
        return container.create_item(body=document), True
    except Exception as exc:
        if _is_cosmos_conflict_error(exc):
            cert_id = str(document["id"])
            event_id = str(document["eventId"])
            return container.read_item(item=cert_id, partition_key=event_id), False
        if _is_cosmos_not_found_error(exc):
            raise VolunteerServiceStoreOperationError(
                "Cosmos DB 志工服務證明容器不存在。請確認 "
                "COSMOS_VOLUNTEER_SERVICE_CERTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise VolunteerServiceStoreOperationError(
                "目前身分沒有 Cosmos DB 志工服務證明容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def list_volunteer_service_cert_documents(
    *,
    container: VolunteerServiceContainer,
    event_id: str,
) -> list[dict[str, Any]]:
    try:
        return list(
            container.query_items(
                query=(
                    "SELECT c.id, c.eventId, c.sourceCompletionCertId, c.number, "
                    "c.kktixId, c.badgeName, c.name, c.email, "
                    "c.serviceOrganization, c.serviceHours, c.serviceStartDate, "
                    "c.serviceEndDate, c.downloadEnabled, c.certStatus, "
                    "c.createdAt FROM c WHERE c.eventId = @eventId "
                    "ORDER BY c.number ASC"
                ),
                parameters=[{"name": "@eventId", "value": event_id}],
                partition_key=event_id,
                enable_cross_partition_query=False,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise VolunteerServiceStoreOperationError(
                "Cosmos DB 志工服務證明容器不存在。請確認 "
                "COSMOS_VOLUNTEER_SERVICE_CERTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise VolunteerServiceStoreOperationError(
                "目前身分沒有 Cosmos DB 志工服務證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise VolunteerServiceStoreOperationError("志工服務證明資料查詢暫時失敗。") from exc


def read_volunteer_service_cert_document(
    *,
    cert_id: str,
    container: VolunteerServiceContainer,
    event_id: str,
) -> dict[str, Any]:
    try:
        document = container.read_item(item=cert_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise VolunteerServiceStoreOperationError("找不到指定志工服務證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise VolunteerServiceStoreOperationError(
                "目前身分沒有 Cosmos DB 志工服務證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise

    if not isinstance(document, dict):
        raise VolunteerServiceStoreOperationError("志工服務證明資料格式不合法。")

    return document


def replace_volunteer_service_cert_document(
    *,
    container: VolunteerServiceContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.replace_item(item=document["id"], body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise VolunteerServiceStoreOperationError("找不到指定志工服務證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise VolunteerServiceStoreOperationError(
                "目前身分沒有 Cosmos DB 志工服務證明容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def get_volunteer_service_store_config() -> VolunteerServiceStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    container_name = _read_env("COSMOS_VOLUNTEER_SERVICE_CERTS_CONTAINER")
    if not endpoint or not database_name or not container_name:
        raise VolunteerServiceStoreConfigurationError(
            "Cosmos DB 志工服務證明容器尚未設定完成。請設定 COSMOS_ENDPOINT、"
            "COSMOS_DATABASE_NAME 與 COSMOS_VOLUNTEER_SERVICE_CERTS_CONTAINER。"
        )

    return VolunteerServiceStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        container_name=container_name,
    )


@lru_cache(maxsize=1)
def get_volunteer_service_certs_container() -> VolunteerServiceContainer:
    config = get_volunteer_service_store_config()
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise VolunteerServiceStoreConfigurationError(
            "缺少 Cosmos DB 套件。請安裝 azure-cosmos 與 azure-identity。"
        ) from exc

    client = CosmosClient(config.endpoint, credential=DefaultAzureCredential())
    database = client.get_database_client(config.database_name)
    return database.get_container_client(config.container_name)


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _is_cosmos_conflict_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 409


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 403
