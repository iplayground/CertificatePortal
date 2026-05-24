from __future__ import annotations

from typing import Any


COMPLETION_METRIC_FIELDS = (
    "totalCount",
    "downloadableCount",
    "downloadCount",
    "verificationCount",
)


def empty_completion_metrics() -> dict[str, int]:
    return {field_name: 0 for field_name in COMPLETION_METRIC_FIELDS}


def summarize_completion_cert_documents(
    documents: list[dict[str, Any]],
) -> dict[str, int]:
    return {
        "totalCount": len(documents),
        "downloadableCount": sum(
            1 for document in documents if is_completion_cert_downloadable(document)
        ),
        "downloadCount": sum(read_completion_cert_download_count(document) for document in documents),
        "verificationCount": sum(
            read_non_negative_int_field(
                document,
                ("verificationCount",),
            )
            for document in documents
        ),
    }


def read_completion_cert_download_count(document: dict[str, Any]) -> int:
    download_count = read_non_negative_int_field(document, ("downloadCount",))
    if download_count > 0:
        return download_count

    return 1 if has_completion_cert_download_record(document) else 0


def is_completion_cert_downloadable(document: dict[str, Any]) -> bool:
    return (
        str(document.get("certStatus", "")).strip() == "issued"
        and str(document.get("issuedPdfBlobName") or "").strip() != ""
    )


def has_completion_cert_download_record(document: dict[str, Any]) -> bool:
    if read_non_negative_int_field(document, ("downloadCount",)) > 0:
        return True

    return any(
        str(document.get(field_name) or "").strip()
        for field_name in ("firstDownloadAt", "lastDownloadAt")
    )


def read_non_negative_int_field(
    document: dict[str, Any],
    field_names: tuple[str, ...],
) -> int:
    for field_name in field_names:
        value = document.get(field_name)
        if isinstance(value, int) and not isinstance(value, bool):
            return max(0, value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return 0


def read_non_negative_counter(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return 0
