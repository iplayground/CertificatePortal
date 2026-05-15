from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BlobStoreConfig:
    account_name: str
    connection_string: str


class BlobStoreConfigurationError(RuntimeError):
    pass


class BlobStoreOperationError(RuntimeError):
    pass


def get_blob_store_config() -> BlobStoreConfig:
    return BlobStoreConfig(
        account_name=(
            _read_env("BLOB_STORAGE_ACCOUNT_NAME")
            or _read_env("AzureWebJobsStorage__accountName")
        ),
        connection_string=_read_env("AzureWebJobsStorage"),
    )


@lru_cache(maxsize=1)
def get_blob_service_client() -> Any:
    config = get_blob_store_config()
    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise BlobStoreConfigurationError(
            "缺少 Azure Blob Storage 套件。請安裝 azure-storage-blob 與 azure-identity。"
        ) from exc

    if config.connection_string:
        return BlobServiceClient.from_connection_string(config.connection_string)

    if not config.account_name:
        raise BlobStoreConfigurationError(
            "Blob Storage 尚未設定完成。請設定 BLOB_STORAGE_ACCOUNT_NAME 或 "
            "AzureWebJobsStorage__accountName。"
        )

    account_url = f"https://{config.account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url, credential=DefaultAzureCredential())


def download_blob_bytes(
    *,
    blob_name: str,
    container_name: str,
) -> bytes:
    try:
        blob_client = (
            get_blob_service_client()
            .get_container_client(container_name)
            .get_blob_client(blob_name)
        )
        return blob_client.download_blob().readall()
    except Exception as exc:
        raise BlobStoreOperationError("Blob 下載失敗。") from exc


def download_blob_to_path(
    *,
    blob_name: str,
    container_name: str,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(
        download_blob_bytes(container_name=container_name, blob_name=blob_name)
    )
    return output_path


def upload_pdf_blob(
    *,
    blob_name: str,
    container_name: str,
    data: bytes,
    standard_blob_tier: str = "Cool",
) -> str:
    try:
        from azure.storage.blob import ContentSettings, StandardBlobTier
    except ImportError as exc:
        raise BlobStoreConfigurationError(
            "缺少 Azure Blob Storage 套件。請安裝 azure-storage-blob。"
        ) from exc

    resolved_blob_tier = resolve_standard_blob_tier(
        standard_blob_tier,
        standard_blob_tier_type=StandardBlobTier,
    )
    try:
        blob_client = (
            get_blob_service_client()
            .get_container_client(container_name)
            .get_blob_client(blob_name)
        )
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type="application/pdf"),
            standard_blob_tier=resolved_blob_tier,
        )
        return blob_name
    except Exception as exc:
        raise BlobStoreOperationError("Blob 上傳失敗。") from exc


def upload_blob_bytes(
    *,
    blob_name: str,
    container_name: str,
    content_type: str,
    data: bytes,
    standard_blob_tier: str = "Cool",
) -> str:
    try:
        from azure.storage.blob import ContentSettings, StandardBlobTier
    except ImportError as exc:
        raise BlobStoreConfigurationError(
            "缺少 Azure Blob Storage 套件。請安裝 azure-storage-blob。"
        ) from exc

    resolved_blob_tier = resolve_standard_blob_tier(
        standard_blob_tier,
        standard_blob_tier_type=StandardBlobTier,
    )
    try:
        blob_client = (
            get_blob_service_client()
            .get_container_client(container_name)
            .get_blob_client(blob_name)
        )
        blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
            standard_blob_tier=resolved_blob_tier,
        )
        return blob_name
    except Exception as exc:
        raise BlobStoreOperationError("Blob 上傳失敗。") from exc


def delete_blob(
    *,
    blob_name: str,
    container_name: str,
) -> None:
    try:
        blob_client = (
            get_blob_service_client()
            .get_container_client(container_name)
            .get_blob_client(blob_name)
        )
        blob_client.delete_blob()
    except Exception as exc:
        status_code = getattr(exc, "status_code", None)
        if status_code == 404:
            return
        raise BlobStoreOperationError("Blob 刪除失敗。") from exc


def resolve_standard_blob_tier(
    value: str,
    *,
    standard_blob_tier_type: Any,
) -> Any:
    normalized_value = value.strip().upper()
    if not normalized_value:
        return standard_blob_tier_type.COOL

    tier = getattr(standard_blob_tier_type, normalized_value, None)
    if tier is None:
        raise BlobStoreConfigurationError("不支援的 Blob 存取層設定。")

    return tier


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()
