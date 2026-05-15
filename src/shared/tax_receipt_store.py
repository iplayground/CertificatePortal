from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.shared.event_store import utc_now_iso


TAX_RECEIPT_NAMESPACE = "io.iplayground.ipg-certificate.tax-receipts"


class TaxReceiptContainer(Protocol):
    def create_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...

    def delete_item(self, item: str, partition_key: str, **kwargs: Any) -> None: ...

    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]: ...

    def replace_item(self, item: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]: ...

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
        **kwargs: Any,
    ) -> Any: ...


@dataclass(frozen=True)
class TaxReceiptStoreConfig:
    endpoint: str
    database_name: str
    container_name: str


class TaxReceiptStoreConfigurationError(RuntimeError):
    pass


class TaxReceiptStoreOperationError(RuntimeError):
    pass


def build_tax_receipt_id(
    idempotency_key: str,
    *,
    actor: str,
    event_id: str,
) -> str:
    namespace_value = (
        f"{TAX_RECEIPT_NAMESPACE}:"
        f"{event_id.strip()}:{actor.strip().lower()}:{idempotency_key.strip()}"
    )
    return f"trec_{uuid5(NAMESPACE_URL, namespace_value)}"


def build_tax_receipt_blob_name(
    *,
    content_type: str,
    event_id: str,
    receipt_id: str,
) -> str:
    extension = resolve_tax_receipt_file_extension(content_type)
    return f"{event_id.strip()}/{receipt_id.strip()}{extension}"


def build_tax_receipt_file_name(
    *,
    content_type: str,
    file_sequence: int,
    tax_id: str,
) -> str:
    return (
        f"receipt-{tax_id.strip()}-{file_sequence}"
        f"{resolve_tax_receipt_file_extension(content_type)}"
    )


def resolve_tax_receipt_file_extension(content_type: str) -> str:
    extension = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }.get(content_type, "")
    return extension


def build_tax_receipt_document(
    *,
    actor: str,
    amount: int,
    content_type: str,
    event_id: str,
    file_name: str,
    file_sequence: int,
    file_size: int,
    generated_at: str,
    receipt_id: str,
    source_blob_name: str,
    tax_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    return {
        "id": receipt_id,
        "eventId": event_id,
        "taxId": tax_id,
        "amount": amount,
        "generatedAt": generated_at,
        "sourceBlobName": source_blob_name,
        "fileName": file_name,
        "fileSequence": file_sequence,
        "contentType": content_type,
        "fileSize": file_size,
        "downloadCount": 0,
        "portalDownloadCount": 0,
        "createdBy": actor,
        "createdAt": timestamp,
        "updatedBy": actor,
        "updatedAt": timestamp,
    }


def list_tax_receipt_documents(
    *,
    container: TaxReceiptContainer,
    event_id: str,
) -> list[dict[str, Any]]:
    try:
        return list(
            container.query_items(
                query=(
                    "SELECT c.id, c.eventId, c.taxId, c.amount, c.generatedAt, "
                    "c.sourceBlobName, c.fileName, c.contentType, c.fileSize, "
                    "c.fileSequence, c.downloadCount, c.portalDownloadCount, "
                    "c.lastDownloadAt, c.lastPortalDownloadAt, c.createdAt, c.updatedAt FROM c "
                    "WHERE c.eventId = @eventId ORDER BY c.generatedAt DESC"
                ),
                parameters=[{"name": "@eventId", "value": event_id}],
                partition_key=event_id,
                enable_cross_partition_query=False,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise TaxReceiptStoreOperationError(
                "Cosmos DB 繳稅證明容器不存在。請確認 COSMOS_TAX_RECEIPTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise TaxReceiptStoreOperationError(
                "目前身分沒有 Cosmos DB 繳稅證明容器讀取權限。"
            ) from exc
        raise TaxReceiptStoreOperationError("繳稅證明資料查詢暫時失敗。") from exc


def read_tax_receipt_document(
    *,
    container: TaxReceiptContainer,
    event_id: str,
    receipt_id: str,
) -> dict[str, Any]:
    try:
        document = container.read_item(item=receipt_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise TaxReceiptStoreOperationError("找不到指定繳稅證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise TaxReceiptStoreOperationError(
                "目前身分沒有 Cosmos DB 繳稅證明容器讀取權限。"
            ) from exc
        raise

    if not isinstance(document, dict):
        raise TaxReceiptStoreOperationError("繳稅證明資料格式不合法。")

    return document


def upsert_tax_receipt_document(
    *,
    container: TaxReceiptContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.upsert_item(body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise TaxReceiptStoreOperationError(
                "Cosmos DB 繳稅證明容器不存在。請確認 COSMOS_TAX_RECEIPTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise TaxReceiptStoreOperationError(
                "目前身分沒有 Cosmos DB 繳稅證明容器寫入權限。"
            ) from exc
        raise TaxReceiptStoreOperationError("繳稅證明資料寫入暫時失敗。") from exc


def replace_tax_receipt_document(
    *,
    container: TaxReceiptContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.replace_item(item=document["id"], body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise TaxReceiptStoreOperationError("找不到指定繳稅證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise TaxReceiptStoreOperationError(
                "目前身分沒有 Cosmos DB 繳稅證明容器更新權限。"
            ) from exc
        raise TaxReceiptStoreOperationError("繳稅證明資料更新暫時失敗。") from exc


def delete_tax_receipt_document(
    *,
    container: TaxReceiptContainer,
    event_id: str,
    receipt_id: str,
) -> None:
    try:
        container.delete_item(item=receipt_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise TaxReceiptStoreOperationError("找不到指定繳稅證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise TaxReceiptStoreOperationError(
                "目前身分沒有 Cosmos DB 繳稅證明容器刪除權限。"
            ) from exc
        raise TaxReceiptStoreOperationError("繳稅證明資料刪除暫時失敗。") from exc


def get_tax_receipt_store_config() -> TaxReceiptStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    container_name = _read_env("COSMOS_TAX_RECEIPTS_CONTAINER")
    if not (endpoint and database_name and container_name):
        raise TaxReceiptStoreConfigurationError(
            "Cosmos DB 繳稅證明容器尚未設定完成。請設定 COSMOS_ENDPOINT、"
            "COSMOS_DATABASE_NAME 與 COSMOS_TAX_RECEIPTS_CONTAINER。"
        )

    return TaxReceiptStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        container_name=container_name,
    )


@lru_cache(maxsize=1)
def get_tax_receipt_database_client() -> Any:
    config = get_tax_receipt_store_config()
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise TaxReceiptStoreConfigurationError(
            "缺少 Cosmos DB 套件。請安裝 azure-cosmos 與 azure-identity。"
        ) from exc

    client = CosmosClient(config.endpoint, credential=DefaultAzureCredential())
    return client.get_database_client(config.database_name)


def get_tax_receipts_container() -> TaxReceiptContainer:
    config = get_tax_receipt_store_config()
    return get_tax_receipt_database_client().get_container_client(config.container_name)


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 403


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()
