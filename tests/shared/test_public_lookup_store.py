from __future__ import annotations

import pytest

from src.shared.public_lookup_store import (
    PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS,
    PublicLookupStoreConfigurationError,
    build_public_lookup_cosmos_timeout_options,
    build_public_lookup_attempt_id,
    get_public_lookup_store_config,
    clear_public_lookup_local_block,
    is_public_lookup_blocked,
    is_public_lookup_blocked_by_local_cache,
    remember_public_lookup_block,
    record_public_lookup_failure,
    record_public_lookup_success,
)


class FakeLookupAttemptsContainer:
    def __init__(self) -> None:
        self.items: dict[str, dict[str, object]] = {}
        self.timeout_options: list[dict[str, object]] = []

    def read_item(self, item: str, partition_key: str, **kwargs: object) -> dict[str, object]:
        raise AssertionError("not used")

    def upsert_item(self, body: dict[str, object], **kwargs: object) -> dict[str, object]:
        self.timeout_options.append(kwargs)
        self.items[str(body["id"])] = body
        return body


def test_build_public_lookup_attempt_id_uses_stable_uuid_without_raw_ip() -> None:
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")

    assert attempt_id == "lookup_f3bba227-7f73-5990-b496-666f49d39ace"
    assert "203.0.113.10" not in attempt_id


def test_build_public_lookup_cosmos_timeout_options_uses_short_timeout() -> None:
    assert build_public_lookup_cosmos_timeout_options() == {
        "timeout": PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS,
        "read_timeout": PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS,
    }


def test_record_public_lookup_failure_blocks_on_fifth_failure_in_24_hours() -> None:
    container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    existing_document = None
    for index in range(5):
        existing_document = record_public_lookup_failure(
            attempt_id=attempt_id,
            container=container,
            existing_document=existing_document,
            ip_address="203.0.113.10",
            now=f"2026-04-29T00:0{index}:00Z",
        )

    assert existing_document["ipAddress"] == "203.0.113.10"
    assert existing_document["failureCount"] == 5
    assert existing_document["blockedUntil"] == "2026-04-30T00:04:00Z"
    assert all(
        option["timeout"] == PUBLIC_LOOKUP_COSMOS_TIMEOUT_SECONDS
        for option in container.timeout_options
    )
    assert is_public_lookup_blocked(
        attempt_document=existing_document,
        now="2026-04-29T00:05:00Z",
    )


def test_public_lookup_local_block_cache_expires() -> None:
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    clear_public_lookup_local_block(attempt_id=attempt_id)

    remember_public_lookup_block(
        attempt_id=attempt_id,
        attempt_document={
            "id": attempt_id,
            "blockedUntil": "2026-04-30T00:04:00Z",
        },
        now="2026-04-29T00:04:00Z",
    )

    assert is_public_lookup_blocked_by_local_cache(
        attempt_id=attempt_id,
        now="2026-04-29T00:05:00Z",
    )
    assert not is_public_lookup_blocked_by_local_cache(
        attempt_id=attempt_id,
        now="2026-04-29T01:04:00Z",
    )


def test_public_lookup_local_block_cache_is_capped_to_1_hour() -> None:
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    clear_public_lookup_local_block(attempt_id=attempt_id)

    remember_public_lookup_block(
        attempt_id=attempt_id,
        attempt_document={
            "id": attempt_id,
            "blockedUntil": "2999-04-30T00:04:00Z",
        },
        now="2026-04-29T00:04:00Z",
    )

    assert is_public_lookup_blocked_by_local_cache(
        attempt_id=attempt_id,
        now="2026-04-29T01:03:59Z",
    )
    assert not is_public_lookup_blocked_by_local_cache(
        attempt_id=attempt_id,
        now="2026-04-29T01:04:00Z",
    )


def test_record_public_lookup_failure_resets_window_after_24_hours() -> None:
    container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")
    existing_document = {
        "id": attempt_id,
        "failureCount": 4,
        "firstFailedAt": "2026-04-28T00:00:00Z",
        "lastFailedAt": "2026-04-28T00:04:00Z",
        "blockedUntil": None,
        "updatedAt": "2026-04-28T00:04:00Z",
    }

    updated_document = record_public_lookup_failure(
        attempt_id=attempt_id,
        container=container,
        existing_document=existing_document,
        ip_address="203.0.113.10",
        now="2026-04-29T00:00:00Z",
    )

    assert updated_document["ipAddress"] == "203.0.113.10"
    assert updated_document["failureCount"] == 1
    assert updated_document["firstFailedAt"] == "2026-04-29T00:00:00Z"
    assert updated_document["blockedUntil"] is None


def test_record_public_lookup_success_resets_failure_state() -> None:
    container = FakeLookupAttemptsContainer()
    attempt_id = build_public_lookup_attempt_id("203.0.113.10")

    document = record_public_lookup_success(
        attempt_id=attempt_id,
        container=container,
        ip_address="203.0.113.10",
        now="2026-04-29T00:10:00Z",
    )

    assert document == {
        "id": attempt_id,
        "ipAddress": "203.0.113.10",
        "failureCount": 0,
        "firstFailedAt": None,
        "lastFailedAt": None,
        "blockedUntil": None,
        "updatedAt": "2026-04-29T00:10:00Z",
    }


def test_get_public_lookup_store_config_reads_container_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("COSMOS_DATABASE_NAME", "ipg-certificate")
    monkeypatch.setenv("COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER", "publicLookupAttempts")

    config = get_public_lookup_store_config()

    assert config.endpoint == "https://cosmos.example"
    assert config.database_name == "ipg-certificate"
    assert config.lookup_attempts_container_name == "publicLookupAttempts"


def test_get_public_lookup_store_config_requires_container_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("COSMOS_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("COSMOS_DATABASE_NAME", "ipg-certificate")
    monkeypatch.delenv("COSMOS_PUBLIC_LOOKUP_ATTEMPTS_CONTAINER", raising=False)

    with pytest.raises(PublicLookupStoreConfigurationError, match="公開查詢限制容器"):
        get_public_lookup_store_config()
