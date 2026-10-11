"""i18n core: locale resolution, t() fallback/format safety, dashboard injection."""

import json

import pytest

from world_intel_mcp import i18n


@pytest.fixture
def fake_catalog(monkeypatch):
    cat = {
        "Hello {name}": "你好 {name}",
        "Total {n}": "總計 {n} 筆 {extra}",  # 譯文多出 placeholder -> 必須回退
        "Plain": "純文字",
    }
    monkeypatch.setattr(i18n, "_load_catalog", lambda locale: cat if locale == "zh-TW" else {})
    monkeypatch.setattr(
        i18n,
        "_load_dashboard_catalog",
        lambda locale: {"LAYERS": "圖層"} if locale == "zh-TW" else {},
    )
    return cat


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "zh-TW"),
        ("", "zh-TW"),
        ("   ", "zh-TW"),
        ("zh-TW", "zh-TW"),
        ("zh_TW", "zh-TW"),
        ("zh-Hant-TW", "zh-TW"),
        ("en", "en"),
        ("EN", "en"),
        ("en_US", "en"),
        ("fr", "zh-TW"),
        ("??", "zh-TW"),
    ],
)
def test_get_locale_resolution(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("WORLD_INTEL_LANG", raising=False)
    else:
        monkeypatch.setenv("WORLD_INTEL_LANG", raw)
    assert i18n.get_locale() == expected


def test_get_locale_is_not_cached(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert i18n.get_locale() == "en"
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.get_locale() == "zh-TW"


def test_t_translates_and_formats(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.t("Plain") == "純文字"
    assert i18n.t("Hello {name}", name="Aiken") == "你好 Aiken"


def test_t_missing_key_returns_msgid(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.t("Not in catalog") == "Not in catalog"
    assert i18n.t("Not {x}", x=1) == "Not 1"


def test_t_english_ignores_catalog(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert i18n.t("Plain") == "Plain"
    assert i18n.t("Hello {name}", name="A") == "Hello A"


def test_t_bad_translation_placeholder_falls_back_to_msgid(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    # 譯文含 {extra}，kwargs 沒給 -> KeyError -> 回退原句格式化
    assert i18n.t("Total {n}", n=5) == "Total 5"


def test_t_remote_values_are_not_reformatted(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    out = i18n.t("Hello {name}", name="{0}[red]{x}")
    assert out == "你好 {0}[red]{x}"


def test_placeholders():
    assert i18n.placeholders("a {x} b {y!r} {x}") == {"x", "y"}
    assert i18n.placeholders("no fields") == set()
    assert i18n.placeholders("{{literal}}") == set()


def test_get_catalog_by_locale(monkeypatch, fake_catalog):
    assert i18n.get_catalog("zh-TW") == fake_catalog
    assert i18n.get_catalog("en") == {}
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.get_dashboard_catalog() == {"LAYERS": "圖層"}


_HTML = (
    '<html lang="en"><head><title>x</title></head><body>'
    '<script src="a.js"></script><script>var a=1;</script></body></html>'
)


def test_render_dashboard_html_zh(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    monkeypatch.setattr(
        i18n,
        "_load_dashboard_catalog",
        lambda locale: {"LAYERS": "圖層", "x": "</script><b>& "},
    )
    out = i18n.render_dashboard_html(_HTML)
    assert '<html lang="zh-Hant-TW">' in out
    assert out.count("window.__I18N__") == 1
    # 注入段在主 <script> 之前、且不含可跳出 script 的字元
    inject = out.split("window.__I18N__ = ", 1)[1].split(";</script>", 1)[0]
    assert "</script>" not in inject and "<" not in inject and " " not in inject
    assert json.loads(inject)["LAYERS"] == "圖層"
    assert json.loads(inject)["x"] == "</script><b>& "
    assert out.index("window.__I18N__") < out.index("var a=1;")


def test_render_dashboard_html_en(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    out = i18n.render_dashboard_html(_HTML)
    assert '<html lang="en">' in out
    assert "window.__I18N__ = {};" in out
