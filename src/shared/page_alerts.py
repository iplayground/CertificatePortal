from __future__ import annotations

from html import escape

from src.shared.i18n import DEFAULT_LOCALE, Locale, get_page_alert_copy

DEFAULT_PAGE_ALERT_TONE = "error"
SUPPORTED_PAGE_ALERT_TONES = frozenset({"error", "info", "success"})


def normalize_page_alert_tone(tone: str) -> str:
    normalized_tone = tone.strip().lower()
    if normalized_tone in SUPPORTED_PAGE_ALERT_TONES:
        return normalized_tone
    return DEFAULT_PAGE_ALERT_TONE


def build_page_alert_html(
    *,
    title: str,
    message: str,
    locale: Locale = DEFAULT_LOCALE,
    tone: str = DEFAULT_PAGE_ALERT_TONE,
    dismiss_label: str | None = None,
    dismiss_aria_label: str | None = None,
    dismiss_delay_ms: int | None = None,
) -> str:
    normalized_tone = normalize_page_alert_tone(tone)
    copy = get_page_alert_copy(locale)
    dismiss_delay_attribute = ""
    if dismiss_delay_ms is not None:
        dismiss_delay_attribute = (
            f' data-page-alert-dismiss-delay="{max(dismiss_delay_ms, 0)}"'
        )
    resolved_dismiss_label = dismiss_label or copy["dismiss_label"]
    resolved_dismiss_aria_label = dismiss_aria_label or copy["dismiss_aria_label"]

    return (
        f'<div class="page-alert" data-page-alert data-page-alert-tone="{normalized_tone}"'
        f'{dismiss_delay_attribute} role="alert" aria-live="assertive">'
        '<div class="page-alert-frame" aria-hidden="true"></div>'
        '<div class="page-alert-content">'
        '<div class="page-alert-body">'
        f'<strong class="page-alert-title">{escape(title)}</strong>'
        f'<p class="page-alert-message">{escape(message)}</p>'
        "</div>"
        '<button class="page-alert-close" type="button" data-page-alert-dismiss '
        f'aria-label="{escape(resolved_dismiss_aria_label)}">'
        f"{escape(resolved_dismiss_label)}"
        "</button>"
        "</div>"
        "</div>"
    )
