from __future__ import annotations

import pytest

from src.shared.portal_google_group_auth import (
    PortalGoogleGroupAuthorizationError,
    get_portal_google_allowed_group_keys,
    is_portal_google_user_in_allowed_group,
)


def test_group_auth_reads_multiple_group_keys_from_new_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "PORTAL_GOOGLE_ALLOWED_GROUP_KEYS",
        "group-one, group-two@example.com\ngroup-three",
    )

    assert get_portal_google_allowed_group_keys("member@example.com") == (
        "group-one@example.com",
        "group-two@example.com",
        "group-three@example.com",
    )


def test_group_auth_authorizes_user_when_any_allowed_group_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "group-one,group-two")

    checked_groups: list[str] = []

    def fake_is_member(*, email: str, group_key: str, access_token: str) -> bool:
        checked_groups.append(group_key)
        assert email == "admin@example.com"
        assert access_token == "google-access-token"
        return group_key == "group-two@example.com"

    monkeypatch.setattr(
        "src.shared.portal_google_group_auth._is_portal_google_user_in_group",
        fake_is_member,
    )

    assert is_portal_google_user_in_allowed_group("admin@example.com", "google-access-token") is True
    assert checked_groups == ["group-one@example.com", "group-two@example.com"]


def test_group_auth_keeps_checking_after_one_allowed_group_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "group-one,group-two")

    checked_groups: list[str] = []

    def fake_is_member(*, email: str, group_key: str, access_token: str) -> bool:
        checked_groups.append(group_key)
        assert email == "admin@example.com"
        assert access_token == "google-access-token"
        if group_key == "group-one@example.com":
            raise PortalGoogleGroupAuthorizationError("無法查看第一個群組。")

        return group_key == "group-two@example.com"

    monkeypatch.setattr(
        "src.shared.portal_google_group_auth._is_portal_google_user_in_group",
        fake_is_member,
    )

    assert is_portal_google_user_in_allowed_group("admin@example.com", "google-access-token") is True
    assert checked_groups == ["group-one@example.com", "group-two@example.com"]


def test_group_auth_raises_when_all_allowed_group_lookups_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "group-one,group-two")

    def fake_is_member(*, email: str, group_key: str, access_token: str) -> bool:
        raise PortalGoogleGroupAuthorizationError("Google 群組查詢失敗。")

    monkeypatch.setattr(
        "src.shared.portal_google_group_auth._is_portal_google_user_in_group",
        fake_is_member,
    )

    with pytest.raises(PortalGoogleGroupAuthorizationError):
        is_portal_google_user_in_allowed_group("admin@example.com", "google-access-token")


def test_group_auth_keeps_full_key_when_value_already_contains_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "group-alias@other-domain.example")

    assert get_portal_google_allowed_group_keys("member@example.com") == ("group-alias@other-domain.example",)


def test_group_auth_reads_short_group_name_without_email_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PORTAL_GOOGLE_ALLOWED_GROUP_KEYS", "group-alias")

    assert get_portal_google_allowed_group_keys() == ("group-alias",)
