import pytest

from src.shared.completion_store import (
    CompletionStoreConfigurationError,
    build_completion_cert_document,
    build_completion_cert_id,
    build_completion_cert_request_document,
    build_completion_cert_request_id,
    get_completion_store_config,
)


def test_build_completion_cert_id_uses_event_and_source_identity() -> None:
    assert build_completion_cert_id(
        event_id="evt_1",
        number=1,
        kktix_id="KKTIX-001",
    ) == build_completion_cert_id(
        event_id="evt_1",
        number=1,
        kktix_id="kktix-001",
    )
    assert build_completion_cert_id(
        event_id="evt_2",
        number=1,
        kktix_id="KKTIX-001",
    ) != build_completion_cert_id(
        event_id="evt_1",
        number=1,
        kktix_id="KKTIX-001",
    )


def test_build_completion_cert_request_id_is_stable_for_retry() -> None:
    assert build_completion_cert_request_id(
        "same-key",
        completion_cert_id="ccert_1",
    ) == build_completion_cert_request_id(
        "same-key",
        completion_cert_id="ccert_1",
    )


def test_build_completion_cert_document_stores_complete_list_row() -> None:
    cert_document = build_completion_cert_document(
        badge_name="Ming",
        cert_id="ccert_1",
        email="ming@example.com",
        event_id="evt_1",
        kktix_id="KKTIX-001",
        name="王小明",
        number=1,
        organization="iPlayground",
        ticket_name="一般票",
        now="2026-04-28T06:02:00Z",
    )

    assert cert_document == {
        "id": "ccert_1",
        "eventId": "evt_1",
        "number": 1,
        "kktixId": "KKTIX-001",
        "badgeName": "Ming",
        "ticketName": "一般票",
        "name": "王小明",
        "organization": "iPlayground",
        "email": "ming@example.com",
        "attendanceStatus": "notCheckedIn",
        "certStatus": "notIssued",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "verificationCount": 0,
        "issuedAt": None,
        "createdAt": "2026-04-28T06:02:00Z",
    }


def test_build_completion_cert_request_document_stores_request_state() -> None:
    request = build_completion_cert_request_document(
        completion_cert_id="ccert_1",
        event_id="evt_1",
        request_id="ccreq_1",
        requester_email="ming@example.com",
        requester_note="姓名打錯",
        now="2026-04-28T06:04:00Z",
    )

    assert request == {
        "id": "ccreq_1",
        "completionCertId": "ccert_1",
        "eventId": "evt_1",
        "status": "pending",
        "requesterEmail": "ming@example.com",
        "requesterNote": "姓名打錯",
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": "2026-04-28T06:04:00Z",
        "updatedAt": "2026-04-28T06:04:00Z",
    }


def test_get_completion_store_config_reads_required_container_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("COSMOS_DATABASE_NAME", "ipg-certificate")
    monkeypatch.setenv("COSMOS_COMPLETION_CERTS_CONTAINER", "completionCerts")
    monkeypatch.setenv(
        "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER",
        "completionCertRequests",
    )

    config = get_completion_store_config()

    assert config.endpoint == "https://cosmos.example"
    assert config.database_name == "ipg-certificate"
    assert config.certs_container_name == "completionCerts"
    assert config.cert_requests_container_name == "completionCertRequests"


def test_get_completion_store_config_requires_all_container_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("COSMOS_DATABASE_NAME", "ipg-certificate")
    monkeypatch.delenv("COSMOS_COMPLETION_CERTS_CONTAINER", raising=False)
    monkeypatch.delenv("COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER", raising=False)

    with pytest.raises(CompletionStoreConfigurationError, match="完訓證明容器"):
        get_completion_store_config()
