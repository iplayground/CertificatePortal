from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared.completion_metrics import (  # noqa: E402
    read_non_negative_int_field,
    summarize_completion_cert_documents,
)
from src.shared.completion_store import (  # noqa: E402
    get_completion_records_container,
)
from src.shared.event_store import (  # noqa: E402
    get_events_container,
    normalize_event_completion_metrics,
    replace_event_completion_metrics,
)


LEGACY_COMPLETION_CERT_FIELDS = ("downloadedAt", "downloadedCount")


def normalize_completion_cert_download_fields(
    document: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    updated_document = dict(document)
    previous_document = dict(document)
    legacy_downloaded_at = _read_non_empty_string(document.get("downloadedAt"))
    first_download_at = _read_non_empty_string(document.get("firstDownloadAt"))
    last_download_at = _read_non_empty_string(document.get("lastDownloadAt"))
    download_count = read_non_negative_int_field(document, ("downloadCount",))
    legacy_download_count = read_non_negative_int_field(document, ("downloadedCount",))

    if download_count <= 0:
        download_count = legacy_download_count
    if download_count <= 0 and (first_download_at or last_download_at or legacy_downloaded_at):
        download_count = 1

    if download_count > 0 and not first_download_at:
        first_download_at = legacy_downloaded_at or last_download_at
    if download_count > 0 and not last_download_at:
        last_download_at = legacy_downloaded_at or first_download_at

    updated_document["downloadCount"] = download_count
    updated_document["firstDownloadAt"] = first_download_at if first_download_at else None
    updated_document["lastDownloadAt"] = last_download_at if last_download_at else None

    for field_name in LEGACY_COMPLETION_CERT_FIELDS:
        updated_document.pop(field_name, None)

    return updated_document, updated_document != previous_document


def _read_non_empty_string(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def list_event_documents(events_container: Any, event_id: str | None) -> list[dict[str, Any]]:
    if event_id:
        return [events_container.read_item(item=event_id, partition_key=event_id)]

    return list(
        events_container.query_items(
            query=(
                "SELECT c.id, c.name, c.documentTypes, c.metrics "
                "FROM c ORDER BY c.createdAt ASC"
            ),
            enable_cross_partition_query=True,
        )
    )


def list_completion_cert_documents_for_event(
    completion_certs_container: Any,
    *,
    event_id: str,
) -> list[dict[str, Any]]:
    return list(
        completion_certs_container.query_items(
            query="SELECT * FROM c WHERE c.eventId = @eventId ORDER BY c.number ASC",
            parameters=[{"name": "@eventId", "value": event_id}],
            partition_key=event_id,
            enable_cross_partition_query=False,
        )
    )


def backfill_completion_cert_metrics(
    *,
    apply: bool,
    event_id: str | None,
) -> dict[str, int]:
    load_local_settings_values()
    events_container = get_events_container()
    completion_certs_container = get_completion_records_container()
    events = list_event_documents(events_container, event_id)
    result = {
        "eventsScanned": 0,
        "eventsUpdated": 0,
        "completionCertsScanned": 0,
        "completionCertsUpdated": 0,
    }

    for event in events:
        current_event_id = str(event.get("id") or "").strip()
        if not current_event_id:
            continue

        result["eventsScanned"] += 1
        documents = list_completion_cert_documents_for_event(
            completion_certs_container,
            event_id=current_event_id,
        )
        normalized_documents: list[dict[str, Any]] = []
        for document in documents:
            result["completionCertsScanned"] += 1
            normalized_document, document_changed = normalize_completion_cert_download_fields(
                document
            )
            normalized_documents.append(normalized_document)
            if document_changed:
                result["completionCertsUpdated"] += 1
                if apply:
                    completion_certs_container.replace_item(
                        item=normalized_document["id"],
                        body=normalized_document,
                    )

        metrics = summarize_completion_cert_documents(normalized_documents)
        current_metrics = normalize_event_completion_metrics(event)
        if current_metrics != metrics:
            result["eventsUpdated"] += 1
            if apply:
                replace_event_completion_metrics(
                    container=events_container,
                    event_id=current_event_id,
                    metrics=metrics,
                )

    return result


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
        description="Backfill completion certificate download and aggregate metrics."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to Cosmos DB. Without this flag the script only reports counts.",
    )
    parser.add_argument(
        "--event-id",
        default=None,
        help="Limit backfill to a single event id.",
    )
    args = parser.parse_args()

    result = backfill_completion_cert_metrics(
        apply=args.apply,
        event_id=args.event_id,
    )
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Mode: {mode}")
    for key, value in result.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
