from __future__ import annotations

from typing import Any

from src.shared.volunteer_service_store import (
    build_volunteer_service_cert_document,
    build_volunteer_service_cert_id,
    create_volunteer_service_cert_document,
    list_volunteer_service_cert_documents,
)


def test_build_volunteer_service_cert_id_uses_source_completion_cert() -> None:
    assert build_volunteer_service_cert_id(
        completion_cert_id="ccert_1",
        event_id="evt_1",
    ) == build_volunteer_service_cert_id(
        completion_cert_id=" ccert_1 ",
        event_id=" evt_1 ",
    )
    assert build_volunteer_service_cert_id(
        completion_cert_id="ccert_2",
        event_id="evt_1",
    ) != build_volunteer_service_cert_id(
        completion_cert_id="ccert_1",
        event_id="evt_1",
    )


def test_build_volunteer_service_cert_document_copies_completion_source_fields() -> None:
    document = build_volunteer_service_cert_document(
        actor="admin@iplayground.io",
        completion_cert={
            "id": "ccert_1",
            "eventId": "evt_1",
            "number": 7,
            "kktixId": "KKTIX-007",
            "badgeName": "Volunteer",
            "name": "王小明",
            "organization": "iPlayground",
            "email": "ming@example.com",
            "attendanceStatus": "checkedIn",
            "createdAt": "2026-04-28T06:02:00Z",
        },
        event={
            "eventStartDate": "2026-07-24",
            "eventEndDate": "2026-07-25",
            "completionHours": 16,
        },
        now="2026-05-25T03:00:00Z",
        volunteer_service_cert_id="vscert_1",
    )

    assert document == {
        "id": "vscert_1",
        "eventId": "evt_1",
        "sourceCompletionCertId": "ccert_1",
        "number": 7,
        "kktixId": "KKTIX-007",
        "badgeName": "Volunteer",
        "name": "王小明",
        "email": "ming@example.com",
        "serviceOrganization": "iPlayground",
        "serviceHours": 16,
        "serviceStartDate": "2026-07-24",
        "serviceEndDate": "2026-07-25",
        "downloadEnabled": True,
        "certStatus": "notIssued",
        "sourceCreatedAt": "2026-04-28T06:02:00Z",
        "createdAt": "2026-05-25T03:00:00Z",
        "createdBy": "admin@iplayground.io",
        "updatedAt": "2026-05-25T03:00:00Z",
        "updatedBy": "admin@iplayground.io",
    }


def test_build_volunteer_service_cert_document_disables_download_when_not_checked_in() -> None:
    document = build_volunteer_service_cert_document(
        actor="admin@iplayground.io",
        completion_cert={
            "id": "ccert_1",
            "eventId": "evt_1",
            "attendanceStatus": "notCheckedIn",
        },
        event={},
        now="2026-05-25T03:00:00Z",
        volunteer_service_cert_id="vscert_1",
    )

    assert document["downloadEnabled"] is False


class FakeVolunteerContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, Any]] = {}

    def create_item(self, body: dict[str, Any]) -> dict[str, Any]:
        if body["id"] in self.items:
            error = RuntimeError("conflict")
            setattr(error, "status_code", 409)
            raise error
        self.items[body["id"]] = body
        return body

    def read_item(self, item: str, partition_key: str) -> dict[str, Any]:
        document = self.items[item]
        assert document["eventId"] == partition_key
        return document

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
    ) -> list[dict[str, Any]]:
        self.last_query = query
        self.last_parameters = parameters
        self.last_partition_key = partition_key
        self.last_enable_cross_partition_query = enable_cross_partition_query
        event_id = next(
            parameter["value"]
            for parameter in parameters or []
            if parameter["name"] == "@eventId"
        )
        return [
            document
            for document in self.items.values()
            if document["eventId"] == event_id
        ]


def test_create_volunteer_service_cert_document_returns_existing_on_retry() -> None:
    container = FakeVolunteerContainer()
    document = {
        "id": "vscert_1",
        "eventId": "evt_1",
        "sourceCompletionCertId": "ccert_1",
    }

    first_document, first_was_created = create_volunteer_service_cert_document(
        container=container,
        document=document,
    )
    second_document, second_was_created = create_volunteer_service_cert_document(
        container=container,
        document=document,
    )

    assert first_document == document
    assert first_was_created is True
    assert second_document == document
    assert second_was_created is False


def test_list_volunteer_service_cert_documents_queries_event_partition() -> None:
    container = FakeVolunteerContainer()
    container.items["vscert_1"] = {
        "id": "vscert_1",
        "eventId": "evt_1",
        "number": 1,
    }

    documents = list_volunteer_service_cert_documents(
        container=container,
        event_id="evt_1",
    )

    assert documents == [{"id": "vscert_1", "eventId": "evt_1", "number": 1}]
    assert "c.serviceOrganization" in container.last_query
    assert "c.downloadEnabled" in container.last_query
    assert "c.ticketName" not in container.last_query
    assert "WHERE c.eventId = @eventId" in container.last_query
    assert container.last_parameters == [{"name": "@eventId", "value": "evt_1"}]
    assert container.last_partition_key == "evt_1"
    assert container.last_enable_cross_partition_query is False
