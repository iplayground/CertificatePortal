from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared.blob_store import (  # noqa: E402
    delete_blob,
    download_blob_bytes,
    get_blob_service_client,
    upload_pdf_blob,
)
from src.shared.completion_store import (  # noqa: E402
    get_completion_records_container,
    replace_completion_cert_document,
)


OLD_COMPLETION_CERT_PREFIX = "evt_"
NEW_COMPLETION_CERT_PREFIX = "completionCert/"


def build_new_issued_pdf_blob_name(old_blob_name: str) -> str:
    normalized_blob_name = old_blob_name.strip()
    if normalized_blob_name.startswith(NEW_COMPLETION_CERT_PREFIX):
        return normalized_blob_name
    return f"{NEW_COMPLETION_CERT_PREFIX}{normalized_blob_name}"


def list_completion_cert_documents_with_legacy_blob_paths(container: Any) -> list[dict[str, Any]]:
    documents = list(
        container.query_items(
            query=(
                "SELECT * FROM c WHERE IS_DEFINED(c.issuedPdfBlobName) "
                "AND NOT IS_NULL(c.issuedPdfBlobName) "
                "AND STARTSWITH(c.issuedPdfBlobName, @legacyPrefix)"
            ),
            parameters=[{"name": "@legacyPrefix", "value": OLD_COMPLETION_CERT_PREFIX}],
            enable_cross_partition_query=True,
        )
    )
    return [document for document in documents if isinstance(document, dict)]


def list_legacy_issued_cert_blob_names(*, container_name: str) -> list[str]:
    container_client = get_blob_service_client().get_container_client(container_name)
    blobs = container_client.list_blobs(name_starts_with=OLD_COMPLETION_CERT_PREFIX)
    return sorted(
        str(blob.name).strip()
        for blob in blobs
        if str(getattr(blob, "name", "")).strip().endswith(".pdf")
    )


def migrate_issued_cert_blob_paths(*, apply: bool) -> dict[str, Any]:
    load_local_settings_values()
    container_name = read_required_env("BLOB_ISSUED_CERT_CONTAINER")
    completion_container = get_completion_records_container()
    documents = list_completion_cert_documents_with_legacy_blob_paths(completion_container)
    legacy_blob_names = list_legacy_issued_cert_blob_names(container_name=container_name)
    documents_by_old_blob_name: dict[str, list[dict[str, Any]]] = {}

    for document in documents:
        old_blob_name = str(document.get("issuedPdfBlobName") or "").strip()
        if not old_blob_name:
            continue
        documents_by_old_blob_name.setdefault(old_blob_name, []).append(document)

    old_blob_names = sorted(set(legacy_blob_names) | set(documents_by_old_blob_name))
    migrations: list[dict[str, Any]] = []

    for old_blob_name in old_blob_names:
        new_blob_name = build_new_issued_pdf_blob_name(old_blob_name)
        if new_blob_name == old_blob_name:
            continue

        referenced_documents = documents_by_old_blob_name.get(old_blob_name, [])
        migration = {
            "certIds": [
                str(document.get("id") or "").strip()
                for document in referenced_documents
            ],
            "eventIds": sorted(
                {
                    str(document.get("eventId") or "").strip()
                    for document in referenced_documents
                }
            ),
            "documentUpdatesCount": len(referenced_documents),
            "oldBlobName": old_blob_name,
            "newBlobName": new_blob_name,
        }
        migrations.append(migration)

        if apply:
            pdf_bytes = download_blob_bytes(
                blob_name=old_blob_name,
                container_name=container_name,
            )
            upload_pdf_blob(
                blob_name=new_blob_name,
                container_name=container_name,
                data=pdf_bytes,
            )
            for document in referenced_documents:
                updated_document = {**document, "issuedPdfBlobName": new_blob_name}
                replace_completion_cert_document(
                    container=completion_container,
                    document=updated_document,
                )
            delete_blob(
                blob_name=old_blob_name,
                container_name=container_name,
            )

    return {
        "apply": apply,
        "containerName": container_name,
        "legacyBlobCount": len(legacy_blob_names),
        "matchedDocuments": len(documents),
        "migrations": migrations,
        "migrationsCount": len(migrations),
    }


def read_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_local_settings_values() -> None:
    local_settings_path = REPO_ROOT / "local.settings.json"
    if not local_settings_path.exists():
        return

    try:
        payload = json.loads(local_settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return

    values = payload.get("Values")
    if not isinstance(values, dict):
        return

    for key, value in values.items():
        if isinstance(key, str) and isinstance(value, str) and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Move issued completion certificate PDFs under completionCert/."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Copy blobs, update Cosmos DB, and delete old blobs. Without this flag only reports planned changes.",
    )
    args = parser.parse_args()

    result = migrate_issued_cert_blob_paths(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
