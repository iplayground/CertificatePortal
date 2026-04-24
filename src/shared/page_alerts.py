from __future__ import annotations

from collections.abc import Mapping
from html import escape

from src.shared.i18n import DEFAULT_LOCALE, Locale, get_page_alert_copy

DEFAULT_PAGE_ALERT_TONE = "error"
SUPPORTED_PAGE_ALERT_TONES = frozenset({"error", "info", "success"})
DEFAULT_PAGE_ALERT_CONTEXT = "default"
DEFAULT_PAGE_ALERT_DISMISS_DELAY_MS = 6000


def normalize_page_alert_tone(tone: str) -> str:
    normalized_tone = tone.strip().lower()
    if normalized_tone in SUPPORTED_PAGE_ALERT_TONES:
        return normalized_tone
    return DEFAULT_PAGE_ALERT_TONE


def resolve_page_alert_dismiss_delay_ms(
    context: str,
    dismiss_delay_ms_by_context: Mapping[str, int | None] | None = None,
    *,
    default_delay_ms: int | None = DEFAULT_PAGE_ALERT_DISMISS_DELAY_MS,
) -> int | None:
    if not dismiss_delay_ms_by_context:
        return default_delay_ms

    normalized_context = context.strip()
    if normalized_context in dismiss_delay_ms_by_context:
        return dismiss_delay_ms_by_context[normalized_context]

    return dismiss_delay_ms_by_context.get(DEFAULT_PAGE_ALERT_CONTEXT, default_delay_ms)


def build_page_alert_html(
    *,
    title: str,
    message: str,
    locale: Locale = DEFAULT_LOCALE,
    tone: str = DEFAULT_PAGE_ALERT_TONE,
    dismiss_label: str | None = None,
    dismiss_aria_label: str | None = None,
    dismiss_delay_ms: int | None = DEFAULT_PAGE_ALERT_DISMISS_DELAY_MS,
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
