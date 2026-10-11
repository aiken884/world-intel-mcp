"""WORLD_INTEL_LANG parsing: POSIX-style locale strings and edge cases."""

import pytest

from world_intel_mcp import i18n


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("en", "en"),
        ("EN", "en"),
        ("en_US.UTF-8", "en"),
        ("en-AU", "en"),
        ("en_GB@euro", "en"),
        ("en_US.UTF-8@euro", "en"),
        ("zh", "zh-TW"),
        ("zh_TW.UTF-8", "zh-TW"),
        ("zh-Hant-TW", "zh-TW"),
        ("zh-CN", "zh-TW"),  # no zh-CN catalog: any zh* is served zh-TW
        ("zh-HK", "zh-TW"),
        ("  en_US  ", "en"),
        # Only the first subtag decides, never a prefix match.
        ("eng", None),
        ("english", None),
        ("fr", None),
        ("fr_FR.UTF-8", None),
        ("??", None),
        ("", None),
        ("   ", None),
    ],
)
def test_resolve_locale(raw, expected):
    assert i18n.resolve_locale(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("en_US.UTF-8", "en"),
        ("en-AU", "en"),
        ("EN", "en"),
        ("en_GB@euro", "en"),
        ("zh_TW.UTF-8", "zh-TW"),
        ("zh-Hant-TW", "zh-TW"),
        ("eng", "zh-TW"),  # unrecognised -> default
        ("fr", "zh-TW"),
        ("", "zh-TW"),
    ],
)
def test_get_locale_uses_resolve_locale(monkeypatch, raw, expected):
    monkeypatch.setenv("WORLD_INTEL_LANG", raw)
    assert i18n.get_locale() == expected


def test_get_locale_unset_is_default(monkeypatch):
    monkeypatch.delenv("WORLD_INTEL_LANG", raising=False)
    assert i18n.get_locale() == "zh-TW"


def test_t_follows_posix_english_locale(monkeypatch):
    """The user-visible effect: en_US.UTF-8 must give English text, not zh."""
    monkeypatch.setenv("WORLD_INTEL_LANG", "en_US.UTF-8")
    assert i18n.t("## Data Gaps") == "## Data Gaps"
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh_TW.UTF-8")
    assert i18n.t("## Data Gaps") != "## Data Gaps"
