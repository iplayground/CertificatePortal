from scripts.backfill_completion_cert_metrics import (
    normalize_completion_cert_download_fields,
)


def test_normalize_completion_cert_download_fields_migrates_legacy_downloaded_at() -> None:
    document, changed = normalize_completion_cert_download_fields(
        {
            "id": "ccert_1",
            "downloadedAt": "2026-05-01T00:00:00Z",
            "verificationCount": 2,
        }
    )

    assert changed is True
    assert document["downloadCount"] == 1
    assert document["firstDownloadAt"] == "2026-05-01T00:00:00Z"
    assert document["lastDownloadAt"] == "2026-05-01T00:00:00Z"
    assert "downloadedAt" not in document
    assert "downloadedCount" not in document
    assert document["verificationCount"] == 2


def test_normalize_completion_cert_download_fields_preserves_current_download_count() -> None:
    document, changed = normalize_completion_cert_download_fields(
        {
            "id": "ccert_1",
            "downloadCount": 3,
            "downloadedCount": 1,
            "firstDownloadAt": "2026-05-01T00:00:00Z",
            "lastDownloadAt": "2026-05-01T00:10:00Z",
        }
    )

    assert changed is True
    assert document["downloadCount"] == 3
    assert document["firstDownloadAt"] == "2026-05-01T00:00:00Z"
    assert document["lastDownloadAt"] == "2026-05-01T00:10:00Z"
    assert "downloadedCount" not in document


def test_normalize_completion_cert_download_fields_adds_empty_current_fields() -> None:
    document, changed = normalize_completion_cert_download_fields({"id": "ccert_1"})

    assert changed is True
    assert document["downloadCount"] == 0
    assert document["firstDownloadAt"] is None
    assert document["lastDownloadAt"] is None
