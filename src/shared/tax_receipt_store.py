from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Any, NoReturn
from uuid import NAMESPACE_URL, uuid5

from azure.cosmos import ContainerProxy, CosmosClient, DatabaseProxy

from src.shared.event_store import utc_now_iso


TAX_RECEIPT_NAMESPACE = "io.iplayground.tax-receipts"
_TAX_RECEIPT_CONTAINER_NOT_FOUND_MESSAGE = (
    "Cosmos DB 繳稅證明容器不存在。請確認 COSMOS_TAX_RECEIPTS_CONTAINER "
    "是否指向已建立的資源。"
)


@dataclass(frozen=True)
class TaxReceiptStoreConfig:
    endpoint: str
    database_name: str
    container_name: str


class TaxReceiptStoreConfigurationError(RuntimeError):
    """Raised when tax receipt Cosmos DB configuration is incomplete."""


class TaxReceiptStoreOperationError(RuntimeError):
    """Raised when tax receipt Cosmos DB operations cannot be completed."""


class _TaxReceiptClientProvider:
    """Thread-safe lazy provider for tax receipt Cosmos DB clients.

    Cached config and client fields are read, initialized, and cleared only while
    holding `_lock`.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._config: TaxReceiptStoreConfig | None = None
        self._cosmos_client: CosmosClient | None = None
        self._database_client: DatabaseProxy | None = None

    def get_config(self) -> TaxReceiptStoreConfig:
        with self._lock:
            if self._config is None:
                self._config = _build_tax_receipt_store_config()
            return self._config

    def get_cosmos_client(self) -> CosmosClient:
        with self._lock:
            if self._cosmos_client is None:
                self._cosmos_client = _build_tax_receipt_cosmos_client(
                    self.get_config()
                )
            return self._cosmos_client

    def get_database_client(self) -> DatabaseProxy:
        with self._lock:
            if self._database_client is None:
                self._database_client = self.get_cosmos_client().get_database_client(
                    self.get_config().database_name
                )
            return self._database_client

    def clear(self) -> None:
        with self._lock:
            self._database_client = None
            self._cosmos_client = None
            self._config = None


_tax_receipt_client_provider_lock = threading.RLock()
_default_tax_receipt_client_provider = _TaxReceiptClientProvider()
_tax_receipt_client_provider_override: _TaxReceiptClientProvider | None = None


def set_tax_receipt_client_provider(provider: _TaxReceiptClientProvider) -> None:
    global _tax_receipt_client_provider_override
    with _tax_receipt_client_provider_lock:
        _tax_receipt_client_provider_override = provider


def reset_tax_receipt_client_provider() -> None:
    global _tax_receipt_client_provider_override
    with _tax_receipt_client_provider_lock:
        _tax_receipt_client_provider_override = None


def get_tax_receipt_client_provider() -> _TaxReceiptClientProvider:
    with _tax_receipt_client_provider_lock:
        return _tax_receipt_client_provider_override or _default_tax_receipt_client_provider


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
    extension_by_content_type = {
        "application/pdf": ".pdf",
        "image/png": ".png",
        "image/jpeg": ".jpg",
    }
    extension = extension_by_content_type.get(content_type)
    if extension is None:
        raise TaxReceiptStoreOperationError(
            f"不支援的繳稅證明內容類型: {content_type}"
        )
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
    timestamp: str | None = None,
) -> dict[str, Any]:
    resolved_timestamp = timestamp or utc_now_iso()
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
        "createdAt": resolved_timestamp,
        "updatedBy": actor,
        "updatedAt": resolved_timestamp,
    }


def _raise_tax_receipt_store_operation_error(
    exc: Exception,
    *,
    default_message: str,
    forbidden_message: str,
    not_found_message: str = _TAX_RECEIPT_CONTAINER_NOT_FOUND_MESSAGE,
) -> NoReturn:
    if _is_cosmos_not_found_error(exc):
        raise TaxReceiptStoreOperationError(not_found_message) from exc
    if _is_cosmos_forbidden_error(exc):
        raise TaxReceiptStoreOperationError(forbidden_message) from exc
    raise TaxReceiptStoreOperationError(default_message) from exc


def _get_generated_at_sort_key(document: dict[str, Any]) -> str:
    generated_at = document.get("generatedAt")
    if isinstance(generated_at, str):
        return generated_at
    raise TaxReceiptStoreOperationError(
        "繳稅證明資料缺少或包含無效的 generatedAt 欄位。"
    )


def _sort_tax_receipts_newest_first(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(documents, key=_get_generated_at_sort_key, reverse=True)


def _sort_tax_receipts_oldest_first(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(documents, key=_get_generated_at_sort_key)


def list_tax_receipt_documents(
    *,
    container: ContainerProxy,
    event_id: str,
) -> list[dict[str, Any]]:
    try:
        items = list(
            container.query_items(
                query=(
                    "SELECT c.id, c.eventId, c.taxId, c.amount, c.generatedAt, "
                    "c.sourceBlobName, c.fileName, c.contentType, c.fileSize, "
                    "c.fileSequence, c.downloadCount, c.portalDownloadCount, "
                    "c.lastDownloadAt, c.lastPortalDownloadAt, c.createdAt, c.updatedAt FROM c "
                    "WHERE c.eventId = @eventId"
                ),
                parameters=[{"name": "@eventId", "value": event_id}],
                partition_key=event_id,
                enable_cross_partition_query=False,
            )
        )
        return _sort_tax_receipts_newest_first(items)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料查詢暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器讀取權限。",
        )


def list_tax_receipt_documents_by_tax_id(
    *,
    container: ContainerProxy,
    event_id: str,
    tax_id: str,
) -> list[dict[str, Any]]:
    try:
        items = list(
            container.query_items(
                query=(
                    "SELECT c.id, c.eventId, c.taxId, c.amount, c.generatedAt, "
                    "c.fileName, c.contentType, c.fileSize, c.fileSequence FROM c "
                    "WHERE c.eventId = @eventId AND c.taxId = @taxId"
                ),
                parameters=[
                    {"name": "@eventId", "value": event_id},
                    {"name": "@taxId", "value": tax_id},
                ],
                partition_key=event_id,
                enable_cross_partition_query=False,
            )
        )
        return _sort_tax_receipts_oldest_first(items)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料查詢暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器讀取權限。",
        )


def read_tax_receipt_document(
    *,
    container: ContainerProxy,
    event_id: str,
    receipt_id: str,
) -> dict[str, Any]:
    try:
        return container.read_item(item=receipt_id, partition_key=event_id)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料讀取暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器讀取權限。",
            not_found_message="找不到指定繳稅證明資料。",
        )


def upsert_tax_receipt_document(
    *,
    container: ContainerProxy,
    document: dict[str, Any],
) -> dict[str, Any]:
    receipt_id = _validate_receipt_id(document)
    try:
        document_to_upsert = dict(document)
        document_to_upsert["id"] = receipt_id
        return container.upsert_item(body=document_to_upsert)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料寫入暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器寫入權限。",
        )


def _validate_receipt_id(document: dict[str, Any]) -> str:
    if "id" not in document:
        raise TaxReceiptStoreOperationError(
            "繳稅證明資料格式不合法：缺少必要欄位 'id'。"
        )
    receipt_id = document["id"]

    if not isinstance(receipt_id, str):
        raise TaxReceiptStoreOperationError(
            "繳稅證明資料格式不合法：欄位 'id' 必須為字串，"
            f"實際為 {type(receipt_id).__name__}。"
        )
    if not receipt_id:
        raise TaxReceiptStoreOperationError(
            "繳稅證明資料格式不合法：欄位 'id' 不可為空字串。"
        )
    return receipt_id


def replace_tax_receipt_document(
    *,
    container: ContainerProxy,
    document: dict[str, Any],
) -> dict[str, Any]:
    receipt_id = _validate_receipt_id(document)
    try:
        return container.replace_item(item=receipt_id, body=document)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料更新暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器更新權限。",
            not_found_message="找不到指定繳稅證明資料。",
        )


def delete_tax_receipt_document(
    *,
    container: ContainerProxy,
    event_id: str,
    receipt_id: str,
) -> None:
    try:
        container.delete_item(item=receipt_id, partition_key=event_id)
    except Exception as exc:
        _raise_tax_receipt_store_operation_error(
            exc,
            default_message="繳稅證明資料刪除暫時失敗。",
            forbidden_message="目前身分沒有 Cosmos DB 繳稅證明容器刪除權限。",
            not_found_message="找不到指定繳稅證明資料。",
        )


def clear_tax_receipt_store_caches() -> None:
    get_tax_receipt_client_provider().clear()


def get_tax_receipt_store_config(*, refresh: bool = False) -> TaxReceiptStoreConfig:
    if refresh:
        clear_tax_receipt_store_caches()
    return get_tax_receipt_client_provider().get_config()


def _build_tax_receipt_store_config() -> TaxReceiptStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    container_name = _read_env("COSMOS_TAX_RECEIPTS_CONTAINER")
    missing_vars = [
        env_name
        for env_name, value in (
            ("COSMOS_ENDPOINT", endpoint),
            ("COSMOS_DATABASE_NAME", database_name),
            ("COSMOS_TAX_RECEIPTS_CONTAINER", container_name),
        )
        if not value
    ]
    if missing_vars:
        raise TaxReceiptStoreConfigurationError(
            "Cosmos DB 繳稅證明容器尚未設定完成。缺少環境變數："
            f"{'、'.join(missing_vars)}。"
        )

    return TaxReceiptStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        container_name=container_name,
    )


def get_tax_receipt_cosmos_client(*, refresh: bool = False) -> CosmosClient:
    if refresh:
        clear_tax_receipt_store_caches()
    return get_tax_receipt_client_provider().get_cosmos_client()


def _build_tax_receipt_cosmos_client(
    config: TaxReceiptStoreConfig,
) -> CosmosClient:
    try:
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise TaxReceiptStoreConfigurationError(
            "缺少 Azure Identity 套件。請安裝 azure-identity。"
        ) from exc

    return CosmosClient(
        config.endpoint,
        credential=DefaultAzureCredential(),
    )


def get_tax_receipt_database_client(*, refresh: bool = False) -> DatabaseProxy:
    if refresh:
        clear_tax_receipt_store_caches()
    return get_tax_receipt_client_provider().get_database_client()


def get_tax_receipts_container() -> ContainerProxy:
    config = get_tax_receipt_store_config()
    return get_tax_receipt_database_client().get_container_client(config.container_name)


def _is_cosmos_status_error(exc: Exception, status_code: int) -> bool:
    exc_status_code = getattr(exc, "status_code", None)
    return isinstance(exc_status_code, int) and exc_status_code == status_code


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    return _is_cosmos_status_error(exc, 404)


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    return _is_cosmos_status_error(exc, 403)


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()
