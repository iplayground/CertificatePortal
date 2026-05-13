from __future__ import annotations

from typing import Any

from azure.storage.blob import StandardBlobTier

from src.shared import blob_store


class FakeBlobClient:
    def __init__(self) -> None:
        self.upload: dict[str, Any] = {}

    def upload_blob(self, data: bytes, **kwargs: Any) -> None:
        self.upload = {"data": data, **kwargs}


class FakeContainerClient:
    def __init__(self, blob_client: FakeBlobClient) -> None:
        self.blob_client = blob_client
        self.blob_name = ""

    def get_blob_client(self, blob_name: str) -> FakeBlobClient:
        self.blob_name = blob_name
        return self.blob_client


class FakeBlobServiceClient:
    def __init__(self, container_client: FakeContainerClient) -> None:
        self.container_client = container_client
        self.container_name = ""

    def get_container_client(self, container_name: str) -> FakeContainerClient:
        self.container_name = container_name
        return self.container_client


def test_upload_pdf_blob_converts_access_tier_to_sdk_enum(
    monkeypatch,
) -> None:
    blob_client = FakeBlobClient()
    container_client = FakeContainerClient(blob_client)
    service_client = FakeBlobServiceClient(container_client)
    monkeypatch.setattr(
        blob_store,
        "get_blob_service_client",
        lambda: service_client,
    )

    blob_name = blob_store.upload_pdf_blob(
        blob_name="evt_1/ccert_1.pdf",
        container_name="issued-certs",
        data=b"%PDF-1.4",
        standard_blob_tier="Cool",
    )

    assert blob_name == "evt_1/ccert_1.pdf"
    assert service_client.container_name == "issued-certs"
    assert container_client.blob_name == "evt_1/ccert_1.pdf"
    assert blob_client.upload["data"] == b"%PDF-1.4"
    assert blob_client.upload["overwrite"] is True
    assert blob_client.upload["content_settings"].content_type == "application/pdf"
    assert blob_client.upload["standard_blob_tier"] is StandardBlobTier.COOL
