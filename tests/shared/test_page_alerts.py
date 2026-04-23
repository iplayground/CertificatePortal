from __future__ import annotations

from src.shared.page_alerts import build_page_alert_html


def test_build_page_alert_html_defaults_to_traditional_chinese_copy() -> None:
    html = build_page_alert_html(
        title="登入未完成",
        message="請再試一次。",
    )

    assert "登入未完成" in html
    assert "請再試一次。" in html
    assert ">知道了<" in html
    assert 'aria-label="關閉提示"' in html


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
