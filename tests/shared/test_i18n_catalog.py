from __future__ import annotations

from json import loads

from src.shared.i18n import LOCALE_DIR, SUPPORTED_LOCALES, load_locale_catalog


def collect_structure_paths(value: object, path: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if isinstance(value, dict):
        paths = {path}

        for key, nested_value in value.items():
            assert isinstance(key, str), f"Locale key path {'/'.join(path) or '<root>'} contains a non-string key."
            paths.update(collect_structure_paths(nested_value, (*path, key)))

        return paths

    assert isinstance(value, str), f"Locale key path {'/'.join(path)} must resolve to a string value."
    return {path}


def test_locale_files_match_supported_locale_list() -> None:
    locale_files = {path.stem for path in LOCALE_DIR.glob("*.json")}
    assert locale_files == set(SUPPORTED_LOCALES)


def test_all_locale_json_files_share_the_same_key_structure() -> None:
    locale_payloads = {
        locale: loads((LOCALE_DIR / f"{locale}.json").read_text(encoding="utf-8"))
        for locale in SUPPORTED_LOCALES
    }

    base_locale = SUPPORTED_LOCALES[0]
    base_payload = locale_payloads[base_locale]
    assert isinstance(base_payload, dict), f"{base_locale}.json must contain a top-level JSON object."

    expected_paths = collect_structure_paths(base_payload)

    for locale, payload in locale_payloads.items():
        assert isinstance(payload, dict), f"{locale}.json must contain a top-level JSON object."
        assert collect_structure_paths(payload) == expected_paths


def test_all_supported_locales_can_load_through_catalog() -> None:
    for locale in SUPPORTED_LOCALES:
        catalog = load_locale_catalog(locale)

        assert catalog.locale_option_labels
        assert catalog.home_page
        assert catalog.verify_page
        assert catalog.page_alert
        assert catalog.completion_certificate_pdf
