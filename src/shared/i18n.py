from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import escape
from http.cookies import SimpleCookie
from json import dumps, loads
from pathlib import Path
from typing import Literal, Mapping

import azure.functions as func

Locale = Literal["zh-TW", "en-US"]

DEFAULT_LOCALE: Locale = "zh-TW"
LOCALE_COOKIE_NAME = "ipg_locale"
LOCALE_COOKIE_MAX_AGE_SECONDS = 31_536_000
SUPPORTED_LOCALES: tuple[Locale, ...] = ("zh-TW", "en-US")
LOCALE_DIR = Path(__file__).resolve().parent / "locales"
HTML_LANGUAGE_TAG_BY_LOCALE: dict[Locale, str] = {
    "zh-TW": "zh-TW",
    "en-US": "en-US",
}
LOCALE_FILE_BY_LOCALE: dict[Locale, Path] = {
    locale: LOCALE_DIR / f"{locale}.json" for locale in SUPPORTED_LOCALES
}
LOCALE_ALIASES: dict[str, Locale] = {
    "zh": "zh-TW",
    "zh-hant": "zh-TW",
    "zh-hant-tw": "zh-TW",
    "zh-hans": "zh-TW",
    "zh-hans-cn": "zh-TW",
    "zh-cn": "zh-TW",
    "zh-sg": "zh-TW",
    "zh-my": "zh-TW",
    "zh-tw": "zh-TW",
    "zh-hk": "zh-TW",
    "zh-mo": "zh-TW",
    "en": "en-US",
    "en-us": "en-US",
}
HOME_PAGE_COPY_KEYS = frozenset(
    {
        "page_title",
        "locale_switcher_label",
        "hero_title",
        "hero_lead",
        "form_title",
        "form_subtitle",
        "event_name_label",
        "event_name_hint",
        "attendee_name_label",
        "attendee_name_placeholder",
        "email_label",
        "email_placeholder",
        "preview_action_label",
        "secondary_note",
        "form_feedback_initial",
        "footnote",
        "copyright_notice",
        "empty_name_text",
        "empty_email_text",
        "preview_feedback_template",
    }
)
VERIFY_PAGE_COPY_KEYS = frozenset(
    {
        "title",
        "cert_id_label",
        "status_label",
        "status_value",
    }
)


@dataclass(frozen=True)
class LocaleCatalog:
    locale_option_labels: dict[Locale, str]
    home_page: dict[str, str]
    verify_page: dict[str, str]


def get_home_page_context(locale: Locale) -> dict[str, str]:
    catalog = load_locale_catalog(locale)

    return {
        **catalog.home_page,
        "html_lang": HTML_LANGUAGE_TAG_BY_LOCALE[locale],
        "current_locale": locale,
        "locale_cookie_name": LOCALE_COOKIE_NAME,
        "locale_cookie_max_age": str(LOCALE_COOKIE_MAX_AGE_SECONDS),
        "current_locale_label": catalog.locale_option_labels[locale],
        "locale_options_html": build_locale_options_html(locale, catalog.locale_option_labels),
        "home_page_i18n_json": get_home_page_i18n_json(),
    }


def get_verify_page_copy(locale: Locale) -> dict[str, str]:
    return load_locale_catalog(locale).verify_page.copy()


def localized_response_headers(locale: Locale) -> dict[str, str]:
    return {
        "Content-Language": HTML_LANGUAGE_TAG_BY_LOCALE[locale],
        "Vary": "Cookie, Accept-Language",
    }


def resolve_locale(req: func.HttpRequest) -> Locale:
    if locale := _resolve_cookie_locale(req.headers):
        return locale

    if locale := _resolve_accept_language_locale(req.headers):
        return locale

    return DEFAULT_LOCALE


def _resolve_cookie_locale(headers: Mapping[str, str]) -> Locale | None:
    cookie_header = _get_header(headers, "Cookie")
    if not cookie_header:
        return None

    cookies = SimpleCookie()
    cookies.load(cookie_header)
    locale_cookie = cookies.get(LOCALE_COOKIE_NAME)
    if locale_cookie is None:
        return None

    return _match_supported_locale(locale_cookie.value)


def _resolve_accept_language_locale(headers: Mapping[str, str]) -> Locale | None:
    accept_language = _get_header(headers, "Accept-Language")
    if not accept_language:
        return None

    weighted_values: list[tuple[float, int, str]] = []

    for index, raw_entry in enumerate(accept_language.split(",")):
        entry = raw_entry.strip()
        if not entry:
            continue

        language_tag, _, params = entry.partition(";")
        quality = 1.0

        for raw_param in params.split(";"):
            param = raw_param.strip()
            if not param.lower().startswith("q="):
                continue

            try:
                quality = float(param[2:])
            except ValueError:
                quality = 0.0
            break

        weighted_values.append((quality, index, language_tag.strip()))

    for _, _, language_tag in sorted(weighted_values, key=lambda item: (-item[0], item[1])):
        if locale := _match_supported_locale(language_tag):
            return locale

    return None


def _match_supported_locale(locale_value: str) -> Locale | None:
    normalized = locale_value.strip().lower()
    if not normalized or normalized == "*":
        return None

    if locale := LOCALE_ALIASES.get(normalized):
        return locale

    primary_language = normalized.split("-", maxsplit=1)[0]
    if primary_language == "en":
        return "en-US"
    if primary_language == "zh":
        return "zh-TW"

    return None


def _get_header(headers: Mapping[str, str], name: str) -> str | None:
    expected_name = name.lower()

    for header_name, header_value in headers.items():
        if header_name.lower() == expected_name:
            return header_value

    return None


def build_locale_options_html(
    current_locale: Locale,
    locale_option_labels: Mapping[Locale, str],
) -> str:
    options_html: list[str] = []

    for locale in SUPPORTED_LOCALES:
        is_current = locale == current_locale
        label = escape(locale_option_labels[locale], quote=True)
        active_class = " is-current" if is_current else ""
        aria_selected = "true" if is_current else "false"

        options_html.append(
            (
                f'<button class="locale-menu-option{active_class}" '
                f'type="button" role="option" aria-selected="{aria_selected}" '
                f'data-locale="{locale}">{label}</button>'
            )
        )

    return "".join(options_html)


@lru_cache(maxsize=1)
def get_home_page_i18n_json() -> str:
    payload = {
        locale: {
            "html_lang": HTML_LANGUAGE_TAG_BY_LOCALE[locale],
            "locale_option_labels": load_locale_catalog(locale).locale_option_labels,
            "home_page": load_locale_catalog(locale).home_page,
        }
        for locale in SUPPORTED_LOCALES
    }

    return dumps(payload, ensure_ascii=False).replace("</", "<\\/")


@lru_cache(maxsize=len(SUPPORTED_LOCALES))
def load_locale_catalog(locale: Locale) -> LocaleCatalog:
    raw_catalog = loads(LOCALE_FILE_BY_LOCALE[locale].read_text(encoding="utf-8"))
    if not isinstance(raw_catalog, dict):
        raise ValueError(f"Locale catalog for {locale} must be a JSON object.")

    return LocaleCatalog(
        locale_option_labels=_validate_locale_option_labels(locale, raw_catalog.get("locale_option_labels")),
        home_page=_validate_string_map(locale, "home_page", raw_catalog.get("home_page"), HOME_PAGE_COPY_KEYS),
        verify_page=_validate_string_map(locale, "verify_page", raw_catalog.get("verify_page"), VERIFY_PAGE_COPY_KEYS),
    )


def _validate_locale_option_labels(
    locale: Locale,
    raw_value: object,
) -> dict[Locale, str]:
    validated = _validate_string_map(
        locale,
        "locale_option_labels",
        raw_value,
        frozenset(SUPPORTED_LOCALES),
    )

    return {
        "zh-TW": validated["zh-TW"],
        "en-US": validated["en-US"],
    }


def _validate_string_map(
    locale: Locale,
    section_name: str,
    raw_value: object,
    required_keys: frozenset[str],
) -> dict[str, str]:
    if not isinstance(raw_value, dict):
        raise ValueError(f"Locale section {section_name!r} for {locale} must be a JSON object.")

    missing_keys = required_keys - raw_value.keys()
    if missing_keys:
        missing_keys_text = ", ".join(sorted(missing_keys))
        raise ValueError(f"Locale section {section_name!r} for {locale} is missing keys: {missing_keys_text}.")

    invalid_keys = [key for key in required_keys if not isinstance(raw_value[key], str)]
    if invalid_keys:
        invalid_keys_text = ", ".join(sorted(invalid_keys))
        raise ValueError(f"Locale section {section_name!r} for {locale} has non-string values: {invalid_keys_text}.")

    return {key: raw_value[key] for key in required_keys}
