import pytest

from src.shared.event_store import (
    EventStoreOperationError,
    build_event_document,
    build_event_id,
    create_event_document,
    list_event_documents,
    list_public_event_documents,
    normalize_event_completion_metrics,
    read_public_event_document,
    update_event_document,
)


class ConflictError(RuntimeError):
    status_code = 409


class NotFoundError(RuntimeError):
    status_code = 404


class ForbiddenError(RuntimeError):
    status_code = 403


class ConflictContainer:
    def __init__(self, existing_item: dict[str, object]) -> None:
        self.existing_item = existing_item

    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise ConflictError()

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        assert item == partition_key == self.existing_item["id"]
        return self.existing_item


class NotFoundContainer:
    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise NotFoundError()

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        raise AssertionError("not found should not attempt idempotent read")


class ForbiddenContainer:
    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise ForbiddenError()

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        raise AssertionError("forbidden should not attempt idempotent read")


class ReplaceContainer:
    def __init__(self, existing_item: dict[str, object]) -> None:
        self.existing_item = existing_item
        self.replaced_item: dict[str, object] | None = None

    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise AssertionError("replace test should not create item")

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        assert item == partition_key == self.existing_item["id"]
        return self.existing_item

    def replace_item(self, item: str, body: dict[str, object]) -> dict[str, object]:
        assert item == self.existing_item["id"]
        self.replaced_item = body
        return body


class ReadContainer:
    def __init__(self, existing_item: dict[str, object] | None) -> None:
        self.existing_item = existing_item

    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise AssertionError("read test should not create item")

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        assert item == partition_key
        if self.existing_item is None:
            raise NotFoundError()

        return self.existing_item


class ForbiddenReadContainer(ReadContainer):
    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        raise ForbiddenError()


class QueryContainer:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items
        self.query = ""
        self.enable_cross_partition_query = False

    def create_item(self, body: dict[str, object]) -> dict[str, object]:
        raise AssertionError("query test should not create item")

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        raise AssertionError("query test should not read item")

    def query_items(
        self,
        query: str,
        *,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, object]]:
        self.query = query
        self.enable_cross_partition_query = enable_cross_partition_query
        return self.items


class ForbiddenQueryContainer(QueryContainer):
    def query_items(
        self,
        query: str,
        *,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, object]]:
        raise ForbiddenError()


def test_build_event_id_is_stable_for_idempotency_key_and_actor() -> None:
    assert build_event_id("same-key", actor="admin@example.com") == build_event_id(
        "same-key",
        actor="ADMIN@example.com",
    )


def test_build_event_document_uses_utc_timestamps_and_actor() -> None:
    event = build_event_document(
        actor="admin@example.com",
        completion_hours=16,
        document_types=["completionCert"],
        event_end_date="2026-07-25",
        event_id="evt_test",
        event_start_date="2026-07-24",
        name="iPlayground 2026",
        status="unlisted",
        completion_cert_download_starts_at="2026-04-27T12:38:00Z",
        now="2026-04-27T12:00:00Z",
    )

    assert event == {
        "id": "evt_test",
        "name": "iPlayground 2026",
        "status": "unlisted",
        "documentTypes": ["completionCert"],
        "eventStartDate": "2026-07-24",
        "eventEndDate": "2026-07-25",
        "completionHours": 16,
        "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
        "volunteerServiceTicketNames": [],
        "metrics": {
            "completionCert": {
                "totalCount": 0,
                "downloadableCount": 0,
                "downloadCount": 0,
                "verificationCount": 0,
            }
        },
        "createdAt": "2026-04-27T12:00:00Z",
        "createdBy": "admin@example.com",
        "updatedAt": "2026-04-27T12:00:00Z",
        "updatedBy": "admin@example.com",
    }


def test_normalize_event_completion_metrics_requires_current_metric_shape() -> None:
    event = {
        "metrics": {
            "completionCert": {
                "totalCount": 5,
                "downloadableCount": 1,
                "downloadCount": 2,
                "verificationCount": 3,
            }
        }
    }

    assert normalize_event_completion_metrics(event) == {
        "totalCount": 5,
        "downloadableCount": 1,
        "downloadCount": 2,
        "verificationCount": 3,
    }


def test_normalize_event_completion_metrics_rejects_missing_current_metric_field() -> None:
    event = {
        "metrics": {
            "completionCert": {
                "totalCount": 5,
                "downloadableCount": 1,
                "verificationCount": 3,
            }
        }
    }

    assert normalize_event_completion_metrics(event) is None


def test_normalize_event_completion_metrics_rejects_extra_legacy_metric_field() -> None:
    event = {
        "metrics": {
            "completionCert": {
                "totalCount": 5,
                "downloadableCount": 1,
                "downloadCount": 2,
                "verificationCount": 3,
                "pendingCount": 4,
            }
        }
    }

    assert normalize_event_completion_metrics(event) is None


def test_create_event_document_returns_existing_item_on_idempotency_conflict() -> None:
    existing_event = {
        "id": "evt_existing",
        "name": "Existing",
    }

    event, was_created = create_event_document(
        container=ConflictContainer(existing_event),
        event_document={"id": "evt_existing", "name": "New"},
    )

    assert event == existing_event
    assert was_created is False


def test_create_event_document_wraps_missing_container_error() -> None:
    with pytest.raises(EventStoreOperationError, match="活動容器不存在"):
        create_event_document(
            container=NotFoundContainer(),
            event_document={"id": "evt_missing"},
        )


def test_create_event_document_wraps_missing_write_permission_error() -> None:
    with pytest.raises(EventStoreOperationError, match="寫入權限"):
        create_event_document(
            container=ForbiddenContainer(),
            event_document={"id": "evt_forbidden"},
        )


def test_update_event_document_replaces_existing_item_without_changing_created_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.shared.event_store.utc_now_iso", lambda: "2026-04-28T06:00:00Z")
    container = ReplaceContainer(
        {
            "id": "evt_existing",
            "name": "Old",
            "status": "unlisted",
            "documentTypes": ["completionCert"],
            "completionCertDownloadStartsAt": "2026-04-27T12:38:00Z",
            "createdAt": "2026-04-27T12:00:00Z",
            "createdBy": "creator@example.com",
            "updatedAt": "2026-04-27T12:00:00Z",
            "updatedBy": "creator@example.com",
        }
    )

    event = update_event_document(
        actor="editor@example.com",
        completion_hours=16,
        completion_cert_download_starts_at=None,
        container=container,
        document_types=["taxReceipt"],
        event_end_date="2026-07-25",
        event_id="evt_existing",
        event_start_date="2026-07-24",
        name="New",
        status="open",
    )

    assert event["id"] == "evt_existing"
    assert event["name"] == "New"
    assert event["status"] == "open"
    assert event["documentTypes"] == ["taxReceipt"]
    assert event["eventStartDate"] == "2026-07-24"
    assert event["eventEndDate"] == "2026-07-25"
    assert event["completionHours"] == 16
    assert event["completionCertDownloadStartsAt"] is None
    assert event["createdAt"] == "2026-04-27T12:00:00Z"
    assert event["createdBy"] == "creator@example.com"
    assert event["updatedAt"] == "2026-04-28T06:00:00Z"
    assert event["updatedBy"] == "editor@example.com"


def test_list_event_documents_queries_events_by_created_at_desc() -> None:
    events = [{"id": "evt_a"}, {"id": "evt_b"}]
    container = QueryContainer(events)

    assert list_event_documents(container=container) == events
    assert container.query == (
        "SELECT c.id, c.name, c.status, c.documentTypes, "
        "c.eventStartDate, c.eventEndDate, c.completionHours, "
        "c.completionCertDownloadStartsAt, "
        "c.volunteerServiceTicketNames, c.metrics "
        "FROM c ORDER BY c.createdAt DESC"
    )
    assert container.enable_cross_partition_query is True


def test_list_public_event_documents_queries_open_events_only() -> None:
    events = [{"id": "evt_a"}, {"id": "evt_b"}]
    container = QueryContainer(events)

    assert list_public_event_documents(container=container) == events
    assert container.query == (
        "SELECT c.id, c.name, c.documentTypes, "
        "c.eventStartDate, c.eventEndDate, c.completionHours, "
        "c.completionCertDownloadStartsAt FROM c "
        "WHERE c.status = 'open' ORDER BY c.createdAt DESC"
    )
    assert container.enable_cross_partition_query is True


def test_read_public_event_document_reads_by_event_id() -> None:
    event = {"id": "evt_a", "status": "open"}

    assert read_public_event_document(container=ReadContainer(event), event_id="evt_a") == event


def test_read_public_event_document_returns_none_when_event_is_missing() -> None:
    assert read_public_event_document(container=ReadContainer(None), event_id="evt_missing") is None


def test_read_public_event_document_wraps_missing_read_permission_error() -> None:
    with pytest.raises(EventStoreOperationError, match="讀取權限"):
        read_public_event_document(
            container=ForbiddenReadContainer(None),
            event_id="evt_forbidden",
        )


def test_list_event_documents_wraps_missing_read_permission_error() -> None:
    with pytest.raises(EventStoreOperationError, match="讀取權限"):
        list_event_documents(container=ForbiddenQueryContainer([]))
