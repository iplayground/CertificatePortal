from __future__ import annotations

from src.shared.page_alerts import build_page_alert_html, resolve_page_alert_dismiss_delay_ms


def test_build_page_alert_html_defaults_to_traditional_chinese_copy() -> None:
    html = build_page_alert_html(
        title="登入未完成",
        message="請再試一次。",
    )

    assert "登入未完成" in html
    assert "請再試一次。" in html
    assert ">知道了<" in html
    assert 'aria-label="關閉提示"' in html
    assert 'data-page-alert-dismiss-delay="6000"' in html


def test_build_page_alert_html_uses_english_copy_when_locale_is_en_us() -> None:
    html = build_page_alert_html(
        title="Sign-in incomplete",
        message="Please try again.",
        locale="en-US",
    )

    assert "Sign-in incomplete" in html
    assert "Please try again." in html
    assert ">Got it<" in html
    assert 'aria-label="Dismiss alert"' in html


def test_build_page_alert_html_allows_explicit_copy_override() -> None:
    html = build_page_alert_html(
        title="Sign-in incomplete",
        message="Please try again.",
        locale="en-US",
        dismiss_label="Close",
        dismiss_aria_label="Close this message",
    )

    assert ">Close<" in html
    assert 'aria-label="Close this message"' in html
    assert ">Got it<" not in html


def test_resolve_page_alert_dismiss_delay_allows_context_overrides() -> None:
    delay_by_context = {
        "default": 7000,
        "home.newsletter-success": 4000,
        "portal.login.not-authorized": 12000,
    }

    assert (
        resolve_page_alert_dismiss_delay_ms(
            "home.newsletter-success",
            delay_by_context,
        )
        == 4000
    )
    assert (
        resolve_page_alert_dismiss_delay_ms(
            "portal.login.not-authorized",
            delay_by_context,
        )
        == 12000
    )
    assert (
        resolve_page_alert_dismiss_delay_ms(
            "unknown-context",
            delay_by_context,
        )
        == 7000
    )


def test_resolve_page_alert_dismiss_delay_defaults_to_six_seconds() -> None:
    assert resolve_page_alert_dismiss_delay_ms("home.notice") == 6000


def test_build_page_alert_html_allows_disabling_auto_dismiss() -> None:
    html = build_page_alert_html(
        title="登入未完成",
        message="請再試一次。",
        dismiss_delay_ms=None,
    )

    assert "data-page-alert-dismiss-delay" not in html
