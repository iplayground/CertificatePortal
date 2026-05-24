import pytest

from src.shared.tax_receipt_store import (
    build_tax_receipt_public_lookup_id,
    build_tax_receipt_blob_name,
    build_tax_receipt_file_name,
    build_tax_receipt_id,
    count_tax_receipt_queried_companies,
    list_tax_receipt_documents,
    list_tax_receipt_documents_by_tax_id,
    record_tax_receipt_public_lookup,
)


class FakeTaxReceiptsContainer:
    def __init__(self, items: list[dict[str, object]]) -> None:
        self.items = items
        self.queries: list[str] = []

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, object]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, object]]:
        self.queries.append(query)
        parameter_values = {
            str(parameter["name"]): parameter["value"]
            for parameter in parameters or []
        }
        assert not enable_cross_partition_query
        assert partition_key == parameter_values["@eventId"]

        items = [
            item
            for item in self.items
            if item["eventId"] == parameter_values["@eventId"]
        ]
        if "STARTSWITH(c.id, 'trlkp_')" in query:
            return [len([item for item in items if str(item["id"]).startswith("trlkp_")])]

        if "STARTSWITH(c.id, 'trec_')" in query:
            items = [item for item in items if str(item["id"]).startswith("trec_")]

        if "@taxId" in parameter_values:
            items = [
                item
                for item in items
                if item["taxId"] == parameter_values["@taxId"]
            ]
        return items

    def read_item(self, item: str, partition_key: str) -> dict[str, object]:
        for document in self.items:
            if document["id"] == item and document["eventId"] == partition_key:
                return dict(document)

        error = RuntimeError("not found")
        setattr(error, "status_code", 404)
        raise error

    def upsert_item(self, body: dict[str, object]) -> dict[str, object]:
        for index, document in enumerate(self.items):
            if document["id"] == body["id"] and document["eventId"] == body["eventId"]:
                self.items[index] = body
                return body

        self.items.append(body)
        return body


def test_build_tax_receipt_id_rejects_whitespace_collisions() -> None:
    with pytest.raises(ValueError, match="event_id"):
        build_tax_receipt_id(
            "receipt-key",
            actor="admin@example.com",
            event_id=" evt_tax",
        )

    with pytest.raises(ValueError, match="actor"):
        build_tax_receipt_id(
            "receipt-key",
            actor="admin@example.com ",
            event_id="evt_tax",
        )

    with pytest.raises(ValueError, match="idempotency_key"):
        build_tax_receipt_id(
            " receipt-key",
            actor="admin@example.com",
            event_id="evt_tax",
        )


@pytest.mark.parametrize(
    ("event_id", "receipt_id"),
    [
        ("../evt_tax", "trec_1"),
        ("evt/tax", "trec_1"),
        ("evt_tax", "../trec_1"),
        ("evt_tax", "trec/1"),
        ("evt_tax ", "trec_1"),
        ("evt_tax", " trec_1"),
    ],
)
def test_build_tax_receipt_blob_name_rejects_unsafe_segments(
    event_id: str,
    receipt_id: str,
) -> None:
    with pytest.raises(ValueError):
        build_tax_receipt_blob_name(
            content_type="application/pdf",
            event_id=event_id,
            receipt_id=receipt_id,
        )


def test_build_tax_receipt_blob_name_uses_valid_segments() -> None:
    assert (
        build_tax_receipt_blob_name(
            content_type="application/pdf",
            event_id="evt_tax",
            receipt_id="trec_1",
        )
        == "evt_tax/trec_1.pdf"
    )


@pytest.mark.parametrize("tax_id", ["../12345678", "123/45678", " 12345678"])
def test_build_tax_receipt_file_name_rejects_unsafe_tax_id(tax_id: str) -> None:
    with pytest.raises(ValueError):
        build_tax_receipt_file_name(
            content_type="image/png",
            file_sequence=1,
            tax_id=tax_id,
        )


def test_build_tax_receipt_file_name_uses_valid_tax_id() -> None:
    assert (
        build_tax_receipt_file_name(
            content_type="image/jpeg",
            file_sequence=2,
            tax_id="12345678",
        )
        == "receipt-12345678-2.jpg"
    )


def test_list_tax_receipt_documents_uses_shared_event_query() -> None:
    container = FakeTaxReceiptsContainer(
        [
            {
                "id": "trec_1",
                "eventId": "evt_tax",
                "taxId": "123",
                "generatedAt": "2026-01-01T00:00:00Z",
            },
            {
                "id": "trec_2",
                "eventId": "other",
                "taxId": "123",
                "generatedAt": "2026-01-02T00:00:00Z",
            },
        ]
    )

    documents = list_tax_receipt_documents(
        container=container,  # type: ignore[arg-type]
        event_id="evt_tax",
    )

    assert [document["id"] for document in documents] == ["trec_1"]
    assert container.queries == [
        (
            "SELECT c.id, c.eventId, c.taxId, c.amount, c.generatedAt, "
            "c.sourceBlobName, c.fileName, c.contentType, c.fileSize, "
            "c.fileSequence, c.downloadCount, c.portalDownloadCount, "
            "c.lastDownloadAt, c.lastPortalDownloadAt, c.createdAt, c.updatedAt "
            "FROM c WHERE c.eventId = @eventId AND STARTSWITH(c.id, 'trec_')"
        )
    ]


def test_list_tax_receipt_documents_by_tax_id_uses_shared_tax_id_query() -> None:
    container = FakeTaxReceiptsContainer(
        [
            {
                "id": "trec_1",
                "eventId": "evt_tax",
                "taxId": "123",
                "generatedAt": "2026-01-01T00:00:00Z",
            },
            {
                "id": "trec_2",
                "eventId": "evt_tax",
                "taxId": "456",
                "generatedAt": "2026-01-02T00:00:00Z",
            },
        ]
    )

    documents = list_tax_receipt_documents_by_tax_id(
        container=container,  # type: ignore[arg-type]
        event_id="evt_tax",
        tax_id="123",
    )

    assert [document["id"] for document in documents] == ["trec_1"]
    assert container.queries == [
        (
            "SELECT c.id, c.eventId, c.taxId, c.amount, c.generatedAt, "
            "c.fileName, c.contentType, c.fileSize, c.fileSequence "
            "FROM c WHERE c.eventId = @eventId AND STARTSWITH(c.id, 'trec_') AND c.taxId = @taxId"
        )
    ]


def test_record_tax_receipt_public_lookup_upserts_stable_company_marker() -> None:
    container = FakeTaxReceiptsContainer([])

    first_document = record_tax_receipt_public_lookup(
        container=container,  # type: ignore[arg-type]
        event_id="evt_tax",
        tax_id="12345678",
        timestamp="2026-05-01T00:00:00Z",
    )
    second_document = record_tax_receipt_public_lookup(
        container=container,  # type: ignore[arg-type]
        event_id="evt_tax",
        tax_id="12345678",
        timestamp="2026-05-02T00:00:00Z",
    )

    assert first_document["id"] == build_tax_receipt_public_lookup_id(
        event_id="evt_tax",
        tax_id="12345678",
    )
    assert first_document["id"] == second_document["id"]
    assert second_document["lookupCount"] == 2
    assert second_document["firstQueriedAt"] == "2026-05-01T00:00:00Z"
    assert second_document["lastQueriedAt"] == "2026-05-02T00:00:00Z"
    assert len(container.items) == 1


def test_count_tax_receipt_queried_companies_counts_lookup_markers() -> None:
    container = FakeTaxReceiptsContainer(
        [
            {"id": "trec_1", "eventId": "evt_tax", "taxId": "12345678"},
            {"id": "trlkp_1", "eventId": "evt_tax", "taxId": "12345678"},
            {"id": "trlkp_2", "eventId": "evt_tax", "taxId": "87654321"},
            {"id": "trlkp_other", "eventId": "evt_other", "taxId": "11112222"},
        ]
    )

    count = count_tax_receipt_queried_companies(
        container=container,  # type: ignore[arg-type]
        event_id="evt_tax",
    )

    assert count == 2
    assert container.queries[-1] == (
        "SELECT VALUE COUNT(1) FROM c "
        "WHERE c.eventId = @eventId "
        "AND STARTSWITH(c.id, 'trlkp_')"
    )
