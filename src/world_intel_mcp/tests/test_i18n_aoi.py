"""zh-TW localization of the AOI brief and the AOI change digest.

Fixed text is translated; data (remote strings, AOI names, counts, ``[n]``
citation numbers, ``sources[].description``) is not.
"""

import re
from pathlib import Path

import pytest

from world_intel_mcp.analysis import aoi
from world_intel_mcp.analysis.aoi import AOIStore
from world_intel_mcp.sources import conflict, news, seismology
from world_intel_mcp.tests.test_aoi import (
    _FAR_LAT,
    _FAR_LON,
    _NEAR_LAT,
    _NEAR_LON,
    _PGH_LAT,
    _PGH_LON,
    _PGH_RADIUS_KM,
    _patch_all_domains,
)

_CITATION = re.compile(r"\[(\d+)\]")


@pytest.fixture
def pgh_store(tmp_path: Path) -> AOIStore:
    s = AOIStore(tmp_path / "i18n_aoi.db")
    s.define("Pittsburgh", _PGH_LAT, _PGH_LON, _PGH_RADIUS_KM)
    yield s
    s.close()


def _use(monkeypatch: pytest.MonkeyPatch, lang: str) -> None:
    monkeypatch.setenv("WORLD_INTEL_LANG", lang)


# ---------------------------------------------------------------------------
# fetch_aoi_brief
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_brief_markdown_is_chinese_and_citations_unchanged(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)

    _use(monkeypatch, "en")
    en = await aoi.fetch_aoi_brief(fetcher, pgh_store, "Pittsburgh")
    _use(monkeypatch, "zh-TW")
    zh = await aoi.fetch_aoi_brief(fetcher, pgh_store, "Pittsburgh")

    md = zh["markdown"]
    assert md.startswith("# 關注區域簡報：Pittsburgh\n")
    assert "中心：40.4406, -79.9959（半徑 50.0 公里）" in md
    for heading in (
        "## 地震",
        "## 軍用航班",
        "## 衝突事件（ACLED）",
        "## 野火",
        "## 航空（抽樣）",
        "## 新聞標題提及",
        "## 軍事基地",
        "## 港口",
        "## 管線",
        "## 核設施",
        "## 海底電纜",
        "## 資料中心",
        "## 太空發射場",
    ):
        assert heading in md, heading
    assert "_範圍內未觀測到。_" in md
    # Domain lines keep the [n] citation and translate the fixed words.
    assert "觀測到 1 架抽樣航空器" in md
    assert "最大 FRP 12.5" in md
    assert "公里）" in md

    for english in (
        "# AOI Brief",
        "## Earthquakes",
        "## Military Flights",
        "## Conflict Events",
        "## Wildfires",
        "## Aviation",
        "## News Headline Mentions",
        "## Military Bases",
        "_None observed in range._",
        "sampled aircraft observed",
        "detections, max FRP",
        "Center:",
    ):
        assert english not in md, english

    # Structure, numbering and verdicts are language-independent.
    assert zh["cited"] is True and en["cited"] is True
    assert zh["counts"] == en["counts"]
    assert _CITATION.findall(md) == _CITATION.findall(en["markdown"])
    assert zh["sources"] == en["sources"]  # descriptions deliberately not translated
    assert zh["news_scoping"] == en["news_scoping"]


@pytest.mark.asyncio
async def test_brief_english_is_unchanged_by_posix_locale_spelling(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "en_US.UTF-8")
    out = await aoi.fetch_aoi_brief(fetcher, pgh_store, "Pittsburgh")
    assert out["markdown"].startswith("# AOI Brief: Pittsburgh\nCenter: ")
    assert "## Earthquakes" in out["markdown"]


@pytest.mark.asyncio
async def test_brief_remote_data_with_braces_and_markup_is_literal(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "zh-TW")

    async def _acled(fetcher, **kwargs):
        return {
            "events": [
                {
                    "event_type": "Protests {0}",
                    "location": "Near {Pgh} [red]x[/red]",
                    "event_date": "2026-08-15",
                    "latitude": _NEAR_LAT,
                    "longitude": _NEAR_LON,
                }
            ],
            "count": 1,
        }

    async def _gdelt(fetcher, **kwargs):
        return {
            "articles": [
                {
                    "title": "Flood {warn} [bold]now[/bold]",
                    "url": "https://news.example/x",
                    "seendate": "20260816T010000Z",
                    "domain": "ex{a}.example",
                }
            ],
            "count": 1,
        }

    async def _eq(fetcher, **kwargs):
        return {"error": "upstream said {0} [red]boom[/red]"}

    monkeypatch.setattr(conflict, "fetch_acled_events", _acled)
    monkeypatch.setattr(news, "fetch_gdelt_search", _gdelt)
    monkeypatch.setattr(seismology, "fetch_earthquakes", _eq)

    out = await aoi.fetch_aoi_brief(fetcher, pgh_store, "Pittsburgh")
    md = out["markdown"]
    assert "Protests {0}，Near {Pgh} [red]x[/red]（" in md
    assert "Flood {warn} [bold]now[/bold]（ex{a}.example）" in md
    assert "## 資料缺口" in md
    assert "- 地震：upstream said {0} [red]boom[/red]" in md
    assert "地震：upstream said {0} [red]boom[/red]" in out["data_gaps"]
    assert out["cited"] is True


@pytest.mark.asyncio
async def test_brief_data_gap_sentences_are_chinese(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from world_intel_mcp.sources import geocode

    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "zh-TW")

    async def _no_place(fetcher, lat, lon):
        return {"error": "nominatim down"}

    async def _mil_partial(fetcher, bboxes):
        # An antimeridian AOI queries two boxes; one failing alone is partial.
        return {"aircraft": [], "partial_errors": ["box 2 timed out"]}

    monkeypatch.setattr(geocode, "fetch_place_context", _no_place)
    monkeypatch.setattr(aoi, "_fetch_military_merged", _mil_partial)

    out = await aoi.fetch_aoi_brief(fetcher, pgh_store, "Pittsburgh")
    gaps = out["data_gaps"]
    assert any(g.startswith("新聞是依關注區域名稱") for g in gaps), gaps
    assert any("反向地理編碼失敗：nominatim down" in g for g in gaps)
    assert "軍用航班：僅部分涵蓋：box 2 timed out" in gaps
    for gap in gaps:
        assert "News is scoped" not in gap
        assert "partial coverage" not in gap


@pytest.mark.asyncio
async def test_brief_polygon_and_corridor_shape_lines_and_bounding_gap(
    fetcher, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "zh-TW")
    s = AOIStore(tmp_path / "shapes.db")
    verts = [[28.5, -96.5], [28.5, -94.0], [30.8, -94.0], [30.8, -96.5]]
    aoi.define_polygon_aoi(s, "Gulf Box", verts)
    aoi.define_corridor_aoi(s, "Gulf Route", [[28.5, -96.5], [30.8, -94.0]], 40.0)

    poly = await aoi.fetch_aoi_brief(fetcher, s, "Gulf Box")
    assert re.search(
        r"^多邊形：4 個頂點（外接中心 [\d.]+, -?[\d.]+；半徑 \d+ 公里）$",
        poly["markdown"],
        re.M,
    ), poly["markdown"][:300]
    assert any(
        g == "管線／海底電纜：以外接圓比對，而非精確的多邊形形狀。"
        for g in poly["data_gaps"]
    ), poly["data_gaps"]
    assert "Polygon:" not in poly["markdown"]

    corr = await aoi.fetch_aoi_brief(fetcher, s, "Gulf Route")
    assert re.search(
        r"^走廊：2 個航點，寬度 40 公里（外接中心 [\d.]+, -?[\d.]+；半徑 \d+ 公里）$",
        corr["markdown"],
        re.M,
    ), corr["markdown"][:300]
    s.close()


def test_infra_labels_are_built_per_call_not_at_import(monkeypatch) -> None:
    """A module-level dict would freeze the import-time locale."""
    _use(monkeypatch, "en")
    assert aoi._infra_labels()["ports"] == "Ports"
    assert aoi._infra_labels()["spaceports"] == "Spaceports"
    _use(monkeypatch, "zh-TW")
    assert aoi._infra_labels()["ports"] == "港口"
    assert aoi._infra_labels()["spaceports"] == "太空發射場"
    assert set(aoi._infra_labels()) == {
        "military_bases",
        "ports",
        "pipelines",
        "nuclear_facilities",
        "undersea_cables",
        "datacenters",
        "spaceports",
    }


# ---------------------------------------------------------------------------
# fetch_aoi_digest (this text is POSTed to the webhook)
# ---------------------------------------------------------------------------


def _quake(qid: str, place: str):
    async def _fake(fetcher, **kwargs):
        return {
            "earthquakes": [
                {
                    "id": qid,
                    "magnitude": 4.5,
                    "place": place,
                    "latitude": _NEAR_LAT,
                    "longitude": _NEAR_LON,
                    "time": "2026-08-15T00:00:00Z",
                },
                {
                    "id": "far",
                    "magnitude": 5.5,
                    "place": "far away",
                    "latitude": _FAR_LAT,
                    "longitude": _FAR_LON,
                },
            ],
            "count": 2,
            "source": "usgs",
        }

    return _fake


@pytest.mark.asyncio
async def test_digest_markdown_is_chinese_across_a_sweep_sequence(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "zh-TW")
    monkeypatch.setattr(seismology, "fetch_earthquakes", _quake("q1", "old {spot}"))

    first = await aoi.fetch_aoi_digest(fetcher, pgh_store)
    assert first["markdown"].startswith("# 關注區域摘要\n")
    assert "## Pittsburgh（圓形）" in first["markdown"]
    assert "_已建立基準；變更將從下次掃描起回報。_" in first["markdown"]

    second = await aoi.fetch_aoi_digest(fetcher, pgh_store)
    assert "_自上次掃描以來無變更。_" in second["markdown"]

    monkeypatch.setattr(seismology, "fetch_earthquakes", _quake("q2", "new {spot}"))
    third = await aoi.fetch_aoi_digest(fetcher, pgh_store)
    md = third["markdown"]
    assert "- 新增 [earthquakes] M4.5 new {spot}（" in md
    assert "- 離開 [earthquakes] M4.5 old {spot}（" in md
    assert third["totals"] == {"new_items": 1, "departed_items": 1}
    for english in ("NEW [", "DEPARTED [", "# AOI Digest", "No changes since"):
        assert english not in md


@pytest.mark.asyncio
async def test_digest_data_gap_and_error_lines_are_chinese(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "zh-TW")

    async def _broken(fetcher, **kwargs):
        return {"error": "ACLED {down} [red]x[/red]"}

    monkeypatch.setattr(conflict, "fetch_acled_events", _broken)
    out = await aoi.fetch_aoi_digest(fetcher, pgh_store)
    assert "- 資料缺口：衝突事件：ACLED {down} [red]x[/red]" in out["markdown"]
    assert "data gap" not in out["markdown"]
    assert out["aois"][0]["data_gaps"] == ["衝突事件：ACLED {down} [red]x[/red]"]


@pytest.mark.asyncio
async def test_digest_english_unchanged(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_all_domains(monkeypatch)
    _use(monkeypatch, "en")
    out = await aoi.fetch_aoi_digest(fetcher, pgh_store)
    assert out["markdown"].startswith("# AOI Digest\n\n## Pittsburgh (circle)\n")
    assert "_Baseline established; changes will report from the next sweep._" in out[
        "markdown"
    ]


@pytest.mark.asyncio
async def test_escalation_data_gaps_are_chinese(
    fetcher, pgh_store: AOIStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    from world_intel_mcp.sources import military

    _use(monkeypatch, "zh-TW")

    async def _broken_acled(fetcher, **kwargs):
        return {"error": "acled {x}"}

    async def _broken_mil(fetcher, bbox=None):
        return {"error": "mil {y}"}

    monkeypatch.setattr(conflict, "fetch_acled_events", _broken_acled)
    monkeypatch.setattr(military, "fetch_military_flights", _broken_mil)
    out = await aoi.fetch_aoi_escalation(fetcher, pgh_store, "Pittsburgh")
    assert "衝突事件：acled {x}" in out["data_gaps"]
    assert "軍用航班：mil {y}" in out["data_gaps"]
