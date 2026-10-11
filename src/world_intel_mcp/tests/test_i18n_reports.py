"""zh-TW localization of the report, daily digest and situation brief."""

import pytest

from world_intel_mcp import reports
from world_intel_mcp.analysis import daily_digest, situation
from world_intel_mcp.analysis.daily_digest import fetch_daily_digest
from world_intel_mcp.locales.zh_TW import MESSAGES
from world_intel_mcp.tests.test_daily_digest import _patch_all_domains


def _metrics() -> dict:
    return {
        "posture_score": 61,
        "risk_level": "elevated",
        "alerts": 3,
        "military_aircraft": 42,
        "conflicts": 7,
        "earthquakes": 5,
        "max_magnitude": 6.1,
        "fire_clusters": 9,
        "cyber_threats": 11,
        "kp_index": 4.0,
        "outbreaks": 2,
        "total_aircraft": 5000,
        "avg_congestion": 33,
        "top_headlines": ["Big headline"],
    }


@pytest.mark.asyncio
async def test_daily_digest_markdown_is_chinese_and_still_cited(
    fetcher, monkeypatch
) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    _patch_all_domains(monkeypatch)

    result = await fetch_daily_digest(fetcher, vector_store=None)

    md = result["markdown"]
    assert "# 每日情報摘要（" in md
    assert "## 各領域重點事件" in md
    assert "## 趨勢（6 小時 vs. 48 小時基準）" in md
    assert "_已省略：向量庫無法使用。_" in md
    assert "**地震** [1]" in md  # 領域標籤已翻譯，引用編號保留
    for english in ("## Top Events by Domain", "## Trends", "Omitted:", "**Earthquakes**"):
        assert english not in md
    assert result["cited"] is True
    assert "向量庫無法使用：已省略趨勢與時間軸" in result["data_gaps"]


@pytest.mark.asyncio
async def test_daily_digest_remote_error_with_braces_is_literal(
    fetcher, monkeypatch
) -> None:
    from world_intel_mcp.sources import cyber

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    _patch_all_domains(monkeypatch)

    async def _broken(fetcher):
        return {"error": "upstream said {0} [red]boom[/red]"}

    monkeypatch.setattr(cyber, "fetch_cyber_threats", _broken)
    result = await fetch_daily_digest(fetcher, vector_store=None)
    assert "網路威脅：upstream said {0} [red]boom[/red]" in result["data_gaps"]


def test_digest_domain_labels_all_translated(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    for key, english in daily_digest._CURRENT_EVENT_DOMAINS.items():
        assert daily_digest._current_event_label(key) != english
        assert english in MESSAGES


def test_situation_prompt_requests_traditional_chinese_only_in_zh(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert "Traditional Chinese" in situation._build_prompt(_metrics(), [])
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert "Traditional Chinese" not in situation._build_prompt(_metrics(), [])


def test_fallback_brief_is_localized_and_keeps_citations(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    text = situation._fallback_brief(_metrics(), {"posture": [1], "alerts": [2]})
    assert "威脅態勢：ELEVATED（分數 61/100），3 則有效警示。[1][2]" in text
    assert "THREAT POSTURE" not in text


def test_extract_metrics_source_descriptions_are_localized(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    data = {
        "earthquakes": {
            "count": 1,
            "earthquakes": [{"magnitude": 6.1, "place": "5km E of Nowhere"}],
        },
        "space_weather": {"current_kp": 5.3},
    }
    _metrics_, sources, _citations = situation._extract_metrics(data)
    descriptions = {s["domain"]: s["description"] for s in sources}
    assert descriptions["earthquakes"] == "規模 M6.1 地震，5km E of Nowhere"
    assert descriptions["space_weather"] == "Kp 指數 5.3"


def test_report_html_is_chinese(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    html = reports._build_html(
        {"world_brief": {"brief": "x"}, "markets": {"quotes": []}}
    )
    assert '<html lang="zh-Hant-TW">' in html
    assert "<h2>執行摘要</h2>" in html
    assert "<h2>金融市場</h2>" in html
    assert "無法取得市場資料" in html
    assert "<h2>Executive Summary</h2>" not in html
    assert "世界情報報告" in html
    assert "PingFang TC" in html  # CJK 字型備援
    assert '"第 " counter(page)' in html


def test_report_html_english_is_unchanged(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    html = reports._build_html({"world_brief": {"brief": "x"}})
    assert '<html lang="en">' in html
    assert "<h2>Executive Summary</h2>" in html
    assert '"Page " counter(page) " of " counter(pages)' in html
    assert "PingFang TC" not in html


def test_report_table_headers_are_translated(monkeypatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    out = reports._render_earthquakes(
        {"earthquakes": [{"properties": {"mag": 5.5, "place": "X", "time": 0}}]}
    )
    assert "<th>規模</th><th>位置</th><th>時間</th>" in out
