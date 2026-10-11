"""Lightweight message catalog.

The msgid is the English source string; a missing translation falls back
to the msgid itself, so an untranslated string shows English instead of
breaking. The locale is re-read from WORLD_INTEL_LANG on every call.
"""

import json
import os
import string
from typing import Any

DEFAULT_LOCALE = "zh-TW"
_HTML_LANG = {"zh-TW": "zh-Hant-TW", "en": "en"}


def resolve_locale(raw: str | None) -> str | None:
    """Map a POSIX/BCP-47-ish language string to a supported locale.

    Drops ``.encoding`` and ``@modifier``, treats ``_`` as ``-``, lowercases,
    then decides on the *first* subtag only (``eng`` is not ``en``). Any
    ``zh*`` is served zh-TW, the only Chinese catalog. Returns None when the
    value is not recognised, so callers can warn before falling back.
    """
    if not raw:
        return None
    tag = raw.strip().split("@", 1)[0].split(".", 1)[0].replace("_", "-").lower()
    first = tag.split("-", 1)[0]
    if first == "en":
        return "en"
    if first == "zh":
        return "zh-TW"
    return None


def get_locale() -> str:
    return resolve_locale(os.environ.get("WORLD_INTEL_LANG")) or DEFAULT_LOCALE


def _load_catalog(locale: str) -> dict[str, str]:
    if locale == "zh-TW":
        from .locales.zh_TW import MESSAGES

        return MESSAGES
    return {}


def _load_dashboard_catalog(locale: str) -> dict[str, str]:
    if locale == "zh-TW":
        from .locales.zh_TW import DASHBOARD

        return DASHBOARD
    return {}


def get_catalog(locale: str | None = None) -> dict[str, str]:
    return _load_catalog(locale or get_locale())


def get_dashboard_catalog(locale: str | None = None) -> dict[str, str]:
    return _load_dashboard_catalog(locale or get_locale())


def placeholders(text: str) -> set[str]:
    return {
        field.split("!")[0].split(":")[0]
        for _, field, _, _ in string.Formatter().parse(text)
        if field
    }


def t(msgid: str, **kwargs: Any) -> str:
    """Translate *msgid*; apply ``str.format(**kwargs)`` if kwargs given.

    A translation whose placeholders do not match kwargs falls back to the
    English msgid so a bad catalog entry can never crash a command.
    """
    text = _load_catalog(get_locale()).get(msgid, msgid)
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        try:
            return msgid.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return msgid


def render_dashboard_html(html: str) -> str:
    """Set <html lang> and inject window.__I18N__ before the main script."""
    locale = get_locale()
    payload = json.dumps(
        _load_dashboard_catalog(locale), ensure_ascii=False, sort_keys=True
    )
    for ch, esc in (
        ("<", "\\u003c"),
        (">", "\\u003e"),
        ("&", "\\u0026"),
        (" ", "\\u2028"),
        (" ", "\\u2029"),
    ):
        payload = payload.replace(ch, esc)
    snippet = f"<script>window.__I18N__ = {payload};</script>\n"
    html = html.replace('<html lang="en">', f'<html lang="{_HTML_LANG[locale]}">', 1)
    return html.replace("<script>", snippet + "<script>", 1)
