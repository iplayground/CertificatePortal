from __future__ import annotations

from html import escape
from re import Match, Pattern, compile
from typing import Mapping

RAW_PLACEHOLDER_PATTERN: Pattern[str] = compile(r"{{{([a-z0-9_]+)}}}")
PLACEHOLDER_PATTERN: Pattern[str] = compile(r"{{([a-z0-9_]+)}}")


def render_html_template(template: str, context: Mapping[str, str]) -> str:
    missing_keys: set[str] = set()

    def replace_raw_placeholder(match: Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        if value is None:
            missing_keys.add(key)
            return match.group(0)

        return value

    def replace_escaped_placeholder(match: Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        if value is None:
            missing_keys.add(key)
            return match.group(0)

        return escape(value, quote=True)

    rendered = RAW_PLACEHOLDER_PATTERN.sub(replace_raw_placeholder, template)
    rendered = PLACEHOLDER_PATTERN.sub(replace_escaped_placeholder, rendered)
    if missing_keys:
        missing_keys_text = ", ".join(sorted(missing_keys))
        raise KeyError(f"Missing template values: {missing_keys_text}")

    return rendered
