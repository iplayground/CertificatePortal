from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared.volunteer_service_store import (  # noqa: E402
    get_volunteer_service_certs_container,
    replace_volunteer_service_cert_document,
)


def list_volunteer_service_documents_with_ticket_name(container: Any) -> list[dict[str, Any]]:
    documents = list(
        container.query_items(
            query=(
                "SELECT * FROM c WHERE IS_DEFINED(c.ticketName) "
                "AND NOT IS_NULL(c.ticketName)"
            ),
            enable_cross_partition_query=True,
        )
    )
    return [document for document in documents if isinstance(document, dict)]


def remove_volunteer_service_ticket_name(*, apply: bool) -> dict[str, Any]:
    load_local_settings_values()
    container = get_volunteer_service_certs_container()
    documents = list_volunteer_service_documents_with_ticket_name(container)
    migrations: list[dict[str, str]] = []

    for document in documents:
        migration = {
            "id": str(document.get("id") or "").strip(),
            "eventId": str(document.get("eventId") or "").strip(),
            "ticketName": str(document.get("ticketName") or ""),
        }
        migrations.append(migration)

        if apply:
            updated_document = {key: value for key, value in document.items() if key != "ticketName"}
            replace_volunteer_service_cert_document(
                container=container,
                document=updated_document,
            )

    return {
        "apply": apply,
        "matchedDocuments": len(documents),
        "migrations": migrations,
        "migrationsCount": len(migrations),
    }


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
        description="Remove ticketName from volunteerServiceCerts documents."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Remove ticketName and replace matching documents. Without this flag only reports planned changes.",
    )
    args = parser.parse_args()

    result = remove_volunteer_service_ticket_name(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
