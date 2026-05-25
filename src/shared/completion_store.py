from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol
from uuid import NAMESPACE_URL, uuid5

from src.shared.cosmos_options import build_public_lookup_cosmos_timeout_options
from src.shared.event_store import utc_now_iso


COMPLETION_CERT_NAMESPACE = "io.iplayground.ipg-certificate.completion-certs"
COMPLETION_CERT_REQUEST_NAMESPACE = "io.iplayground.ipg-certificate.completion-cert-requests"


class CompletionContainer(Protocol):
    def create_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def read_item(self, item: str, partition_key: str, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def replace_item(self, item: str, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def upsert_item(self, body: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError

    def query_items(
        self,
        query: str,
        *,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
        enable_cross_partition_query: bool,
        **kwargs: Any,
    ) -> Any:
        raise NotImplementedError


@dataclass(frozen=True)
class CompletionStoreConfig:
    endpoint: str
    database_name: str
    certs_container_name: str
    cert_requests_container_name: str


class CompletionStoreConfigurationError(RuntimeError):
    pass


class CompletionStoreOperationError(RuntimeError):
    pass


def build_completion_cert_id(
    *,
    event_id: str,
    number: int,
    kktix_id: str,
) -> str:
    normalized_event_id = event_id.strip()
    normalized_number = str(number)
    normalized_kktix_id = kktix_id.strip().lower()
    namespace_value = (
        f"{COMPLETION_CERT_NAMESPACE}:"
        f"{normalized_event_id}:{normalized_number}:{normalized_kktix_id}"
    )
    return f"ccert_{uuid5(NAMESPACE_URL, namespace_value)}"


def build_completion_cert_request_id(
    idempotency_key: str,
    *,
    completion_cert_id: str,
) -> str:
    normalized_cert_id = completion_cert_id.strip()
    normalized_key = idempotency_key.strip()
    namespace_value = (
        f"{COMPLETION_CERT_REQUEST_NAMESPACE}:"
        f"{normalized_cert_id}:{normalized_key}"
    )
    return f"ccreq_{uuid5(NAMESPACE_URL, namespace_value)}"


def build_completion_cert_document(
    *,
    badge_name: str,
    cert_id: str,
    email: str,
    event_id: str,
    kktix_id: str,
    name: str,
    number: int,
    ticket_name: str,
    organization: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    return {
        "id": cert_id,
        "eventId": event_id,
        "number": number,
        "kktixId": kktix_id,
        "badgeName": badge_name,
        "ticketName": ticket_name,
        "name": name,
        "organization": organization,
        "email": email,
        "attendanceStatus": "notCheckedIn",
        "certStatus": "notIssued",
        "issuedPdfBlobName": None,
        "verificationTokenHash": None,
        "downloadCount": 0,
        "firstDownloadAt": None,
        "lastDownloadAt": None,
        "verificationCount": 0,
        "issuedAt": None,
        "createdAt": timestamp,
    }


def list_completion_cert_documents(
    *,
    container: CompletionContainer,
    event_id: str,
) -> list[dict[str, Any]]:
    try:
        return list(
            container.query_items(
                query=(
                    "SELECT c.id, c.eventId, c.number, c.kktixId, c.badgeName, "
                    "c.ticketName, c.name, c.organization, c.email, c.attendanceStatus, "
                    "c.certStatus, c.issuedPdfBlobName, c.verificationTokenHash, "
                    "c.downloadCount, c.firstDownloadAt, c.lastDownloadAt, "
                    "c.verificationCount, c.issuedAt, c.transferredToDocumentType, "
                    "c.transferredToDocumentId, c.transferredAt, c.createdAt FROM c "
                    "WHERE c.eventId = @eventId "
                    "AND (NOT IS_DEFINED(c.documentType) OR c.documentType = @documentType) "
                    "ORDER BY c.number ASC"
                ),
                parameters=[
                    {"name": "@eventId", "value": event_id},
                    {"name": "@documentType", "value": "completionCert"},
                ],
                partition_key=event_id,
                enable_cross_partition_query=False,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明容器不存在。請確認 COSMOS_COMPLETION_CERTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise CompletionStoreOperationError("完訓證明資料查詢暫時失敗。") from exc


def read_completion_cert_document(
    *,
    cert_id: str,
    container: CompletionContainer,
    event_id: str,
) -> dict[str, Any]:
    try:
        document = container.read_item(item=cert_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError("找不到指定完訓證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise

    if not isinstance(document, dict):
        raise CompletionStoreOperationError("完訓證明資料格式不合法。")

    return document


def find_completion_cert_document_for_public_lookup(
    *,
    container: CompletionContainer,
    email: str,
    event_id: str,
    number: int,
) -> dict[str, Any] | None:
    normalized_email = email.strip().lower()
    try:
        documents = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.eventId, c.number, c.email, c.badgeName, "
                    "c.ticketName, c.name, c.organization, c.certStatus, "
                    "c.issuedPdfBlobName, c.transferredToDocumentType, "
                    "c.transferredToDocumentId "
                    "FROM c WHERE c.eventId = @eventId "
                    "AND c.number = @number "
                    "AND (NOT IS_DEFINED(c.documentType) OR c.documentType = @documentType)"
                ),
                parameters=[
                    {"name": "@eventId", "value": event_id},
                    {"name": "@number", "value": number},
                    {"name": "@documentType", "value": "completionCert"},
                ],
                partition_key=event_id,
                enable_cross_partition_query=False,
                **build_public_lookup_cosmos_timeout_options(),
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明容器不存在。請確認 COSMOS_COMPLETION_CERTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise

    document = next(
        (
            candidate
            for candidate in documents
            if isinstance(candidate, dict)
            and str(candidate.get("email", "")).strip().lower() == normalized_email
        ),
        None,
    )

    return document


def find_issued_completion_cert_document_by_verification_token(
    *,
    container: CompletionContainer,
    verification_token: str,
) -> dict[str, Any] | None:
    normalized_token = verification_token.strip()
    if not normalized_token:
        return None

    try:
        documents = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.eventId, c.number, c.kktixId, c.certStatus, "
                    "c.verificationTokenHash, c.certificateDisplayName, "
                    "c.certificateDisplayOrganization, c.certificateLocale, c.issuedAt "
                    "FROM c WHERE c.verificationTokenHash = @verificationToken "
                    "AND c.certStatus = @issuedStatus"
                ),
                parameters=[
                    {"name": "@verificationToken", "value": normalized_token},
                    {"name": "@issuedStatus", "value": "issued"},
                ],
                enable_cross_partition_query=True,
                **build_public_lookup_cosmos_timeout_options(),
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明容器不存在。請確認 COSMOS_COMPLETION_CERTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise CompletionStoreOperationError("完訓證明驗證資料查詢暫時失敗。") from exc

    document = documents[0] if documents else None
    return document if isinstance(document, dict) else None


def replace_completion_cert_document(
    *,
    container: CompletionContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.replace_item(item=document["id"], body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError("找不到指定完訓證明資料。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def upsert_completion_cert_request_document(
    *,
    container: CompletionContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.upsert_item(body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明修改申請容器不存在。請確認 "
                "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def list_completion_cert_request_documents(
    *,
    container: CompletionContainer,
    status: str = "pending",
) -> list[dict[str, Any]]:
    if status == "completed":
        query = (
            "SELECT c.id, c.completionCertId, c.eventId, c.status, "
            "c.requesterEmail, c.requesterNote, c.reviewedBy, c.reviewedAt, "
            "c.reviewCompletedNotifiedAt, c.reviewNote, c.createdAt, c.updatedAt "
            "FROM c WHERE c.status = @approvedStatus OR c.status = @rejectedStatus "
            "OR c.status = @transferredStatus OR c.status = @cancelledByIssueStatus "
            "ORDER BY c.reviewedAt DESC"
        )
        parameters = [
            {"name": "@approvedStatus", "value": "approved"},
            {"name": "@rejectedStatus", "value": "rejected"},
            {"name": "@transferredStatus", "value": "transferred"},
            {"name": "@cancelledByIssueStatus", "value": "cancelledByIssue"},
        ]
    else:
        query = (
            "SELECT c.id, c.completionCertId, c.eventId, c.status, "
            "c.requesterEmail, c.requesterNote, c.reviewedBy, c.reviewedAt, "
            "c.reviewCompletedNotifiedAt, c.reviewNote, c.createdAt, c.updatedAt "
            "FROM c WHERE c.status = @status ORDER BY c.createdAt DESC"
        )
        parameters = [{"name": "@status", "value": status}]

    try:
        return list(
            container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True,
            )
        )
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明修改申請容器不存在。請確認 "
                "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise CompletionStoreOperationError("完訓證明修改申請查詢暫時失敗。") from exc


def read_pending_completion_cert_request_document(
    *,
    container: CompletionContainer,
    completion_cert_id: str,
) -> dict[str, Any] | None:
    try:
        documents = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.completionCertId, c.eventId, c.status, "
                    "c.requesterEmail, c.requesterNote, c.reviewedBy, c.reviewedAt, "
                    "c.reviewCompletedNotifiedAt, c.reviewNote, c.createdAt, c.updatedAt "
                    "FROM c WHERE c.completionCertId = @completionCertId "
                    "AND c.status = @pendingStatus ORDER BY c.createdAt DESC"
                ),
                parameters=[
                    {"name": "@completionCertId", "value": completion_cert_id},
                    {"name": "@pendingStatus", "value": "pending"},
                ],
                enable_cross_partition_query=True,
            )
        )
        return documents[0] if documents else None
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明修改申請容器不存在。請確認 "
                "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise CompletionStoreOperationError("完訓證明修改申請查詢暫時失敗。") from exc


def has_completed_completion_cert_request_document(
    *,
    container: CompletionContainer,
    completion_cert_id: str,
) -> bool:
    return (
        read_completed_completion_cert_request_document(
            container=container,
            completion_cert_id=completion_cert_id,
        )
        is not None
    )


def read_completed_completion_cert_request_document(
    *,
    container: CompletionContainer,
    completion_cert_id: str,
) -> dict[str, Any] | None:
    try:
        documents = list(
            container.query_items(
                query=(
                    "SELECT TOP 1 c.id, c.status, c.reviewedAt, c.reviewNote FROM c "
                    "WHERE c.completionCertId = @completionCertId "
                    "AND (c.status = @approvedStatus OR c.status = @rejectedStatus) "
                    "ORDER BY c.reviewedAt DESC"
                ),
                parameters=[
                    {"name": "@completionCertId", "value": completion_cert_id},
                    {"name": "@approvedStatus", "value": "approved"},
                    {"name": "@rejectedStatus", "value": "rejected"},
                ],
                enable_cross_partition_query=True,
            )
        )
        return documents[0] if documents else None
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明修改申請容器不存在。請確認 "
                "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER 是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise CompletionStoreOperationError("完訓證明修改申請查詢暫時失敗。") from exc


def read_completion_cert_request_document(
    *,
    container: CompletionContainer,
    event_id: str,
    request_id: str,
) -> dict[str, Any]:
    try:
        document = container.read_item(item=request_id, partition_key=event_id)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError("找不到指定完訓證明修改申請。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器讀取權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Reader 或 Data Contributor 權限。"
            ) from exc
        raise

    if not isinstance(document, dict):
        raise CompletionStoreOperationError("完訓證明修改申請格式不合法。")

    return document


def replace_completion_cert_request_document(
    *,
    container: CompletionContainer,
    document: dict[str, Any],
) -> dict[str, Any]:
    try:
        return container.replace_item(item=document["id"], body=document)
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError("找不到指定完訓證明修改申請。") from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明修改申請容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise


def upsert_completion_cert_documents(
    *,
    container: CompletionContainer,
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    saved_documents: list[dict[str, Any]] = []
    try:
        for document in documents:
            saved_documents.append(container.upsert_item(body=document))
    except Exception as exc:
        if _is_cosmos_not_found_error(exc):
            raise CompletionStoreOperationError(
                "Cosmos DB 完訓證明容器不存在。請確認 COSMOS_COMPLETION_CERTS_CONTAINER "
                "是否指向已建立的資源。"
            ) from exc
        if _is_cosmos_forbidden_error(exc):
            raise CompletionStoreOperationError(
                "目前身分沒有 Cosmos DB 完訓證明容器寫入權限。請確認本機或服務身分"
                "已具備 Cosmos DB SQL Data Contributor 權限。"
            ) from exc
        raise

    return saved_documents


def build_completion_cert_request_document(
    *,
    completion_cert_id: str,
    event_id: str,
    request_id: str,
    requester_email: str,
    requester_note: str,
    now: str | None = None,
) -> dict[str, Any]:
    timestamp = now or utc_now_iso()
    return {
        "id": request_id,
        "completionCertId": completion_cert_id,
        "eventId": event_id,
        "status": "pending",
        "requesterEmail": requester_email,
        "requesterNote": requester_note,
        "reviewedBy": None,
        "reviewedAt": None,
        "reviewCompletedNotifiedAt": None,
        "reviewNote": None,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }


def get_completion_store_config() -> CompletionStoreConfig:
    endpoint = _read_env("COSMOS_ENDPOINT")
    database_name = _read_env("COSMOS_DATABASE_NAME")
    certs_container_name = _read_env("COSMOS_COMPLETION_CERTS_CONTAINER")
    cert_requests_container_name = _read_env("COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER")
    if not (
        endpoint
        and database_name
        and certs_container_name
        and cert_requests_container_name
    ):
        raise CompletionStoreConfigurationError(
            "Cosmos DB 完訓證明容器尚未設定完成。請設定 COSMOS_ENDPOINT、"
            "COSMOS_DATABASE_NAME、COSMOS_COMPLETION_CERTS_CONTAINER 與 "
            "COSMOS_COMPLETION_CERT_REQUESTS_CONTAINER。"
        )

    return CompletionStoreConfig(
        endpoint=endpoint,
        database_name=database_name,
        certs_container_name=certs_container_name,
        cert_requests_container_name=cert_requests_container_name,
    )


@lru_cache(maxsize=1)
def get_completion_database_client() -> Any:
    config = get_completion_store_config()
    try:
        from azure.cosmos import CosmosClient
        from azure.identity import DefaultAzureCredential
    except ImportError as exc:
        raise CompletionStoreConfigurationError(
            "缺少 Cosmos DB 套件。請安裝 azure-cosmos 與 azure-identity。"
        ) from exc

    client = CosmosClient(config.endpoint, credential=DefaultAzureCredential())
    return client.get_database_client(config.database_name)


def get_completion_records_container() -> CompletionContainer:
    config = get_completion_store_config()
    return get_completion_database_client().get_container_client(config.certs_container_name)


def get_completion_cert_requests_container() -> CompletionContainer:
    config = get_completion_store_config()
    return get_completion_database_client().get_container_client(
        config.cert_requests_container_name
    )


def _read_env(env_name: str) -> str:
    return os.getenv(env_name, "").strip()


def _is_cosmos_not_found_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 404


def _is_cosmos_forbidden_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    return status_code == 403
