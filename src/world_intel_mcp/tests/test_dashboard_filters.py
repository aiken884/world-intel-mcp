"""Region presets and time-window buttons of the dashboard layer panel.

Both button groups used to be inert: the markup existed upstream but no JS
listened to it, and ``_withinTimeWindow`` hard-coded seven days.  The
dashboard is one static HTML file, so these tests slice the filter block (and
the update functions that consume it) out of ``index.html`` and run them under
``node`` against a minimal fake DOM and a fake Leaflet map.  Assertions are on
observable behaviour: which bounds the map was told to fit, which button is
active, how many items each layer keeps.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from world_intel_mcp import i18n
from world_intel_mcp.locales import zh_TW

INDEX_HTML = Path(i18n.__file__).parent / "dashboard" / "index.html"
SRC = INDEX_HTML.read_text(encoding="utf-8")
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

BLOCK_START = "// ════════════ REGION & TIME FILTERS ════════════"
BLOCK_END = "// ════════════ END REGION & TIME FILTERS ════════════"


def _slice(start: str, end: str) -> str:
    i = SRC.index(start)
    j = SRC.index(end, i)
    return SRC[i:j]


def _run(tmp_path: Path, script: str) -> dict:
    f = tmp_path / "case.js"
    f.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [NODE, str(f)], capture_output=True, text=True, timeout=30, check=False
    )
    assert proc.returncode == 0, proc.stderr[-2500:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


# 2026-10-11T12:00:00Z, the "now" every case runs at.
NOW = "2026-10-11T12:00:00Z"

_HARNESS = r"""
const vm = require('vm');
const NOW = Date.parse(%(now)s);
Date.now = () => NOW;

function El(attrs, text) {
    this._a = Object.assign({}, attrs || {});
    this._cls = new Set(String(this._a.class || '').split(/\s+/).filter(Boolean));
    this.textContent = text || '';
    this._h = {};
    this.classList = {
        add: (c) => this._cls.add(c),
        remove: (c) => this._cls.delete(c),
        contains: (c) => this._cls.has(c),
    };
}
El.prototype.getAttribute = function (k) { return Object.prototype.hasOwnProperty.call(this._a, k) ? this._a[k] : null; };
El.prototype.setAttribute = function (k, v) { this._a[k] = String(v); };
El.prototype.addEventListener = function (t, f) { (this._h[t] = this._h[t] || []).push(f); };
El.prototype.click = function () { (this._h.click || []).forEach((f) => f.call(this, { target: this, preventDefault() {} })); };
El.prototype.active = function () { return this._cls.has('active'); };

// Button text is already the zh-TW translation: nothing may key off it.
const REGIONS = [['global', '地球'], ['americas', '美洲'], ['europe', '歐洲'],
                 ['mena', '中東與北非'], ['asia', '亞太'], ['africa', '非洲']];
const HOURS = [['1', '1h'], ['6', '6h'], ['24', '24h'], ['168', '7d'], ['0', '全部']];
const regionBtns = REGIONS.map(([k, label]) =>
    new El({ class: 'rgn-btn' + (k === 'global' ? ' active' : ''), 'data-region': k }, label));
const hourBtns = HOURS.map(([k, label]) =>
    new El({ class: 'rgn-btn' + (k === '24' ? ' active' : ''), 'data-hours': k }, label));

global.$$ = (sel) => {
    if (sel.indexOf('#regionPresets') >= 0) return regionBtns;
    if (sel.indexOf('#timeFilter') >= 0) return hourBtns;
    return [];
};
global.$ = () => new El();
global.window = { innerWidth: 1440, innerHeight: 900 };
global.document = { getElementById: () => null };
global.setTimeout = (f) => 0;

const calls = [];
global.map = {
    setView(c, z, o) { calls.push({ fn: 'setView', c, z, o }); },
    fitBounds(b, o) { calls.push({ fn: 'fitBounds', b, o }); },
};
global.latestData = null;
const redraws = [];
['updateMapQuakes', 'updateMapConflict', 'updateMapNews', 'updateHudStats', 'updateTicker']
    .forEach((n) => { global[n] = (arg) => redraws.push({ fn: n, arg }); });
// A redraw must reuse latestData: nothing here may hit the network or rebuild
// the whole dashboard (which would re-add every static layer).
const forbidden = [];
global.updateAll = () => forbidden.push('updateAll');
global.fetch = () => { forbidden.push('fetch'); };
global.EventSource = function () { forbidden.push('EventSource'); };

const store = {};
global.localStorage = {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null),
    setItem: (k, v) => { store[k] = String(v); },
};
function breakStorage() {
    Object.defineProperty(global, 'localStorage', {
        configurable: true,
        get() { throw new Error('SecurityError'); },
    });
}
const BLOCK = %(block)s;
function load() { vm.runInThisContext(BLOCK); }
"""


def _script(checks: str, *, now: str = NOW) -> str:
    block = _slice(BLOCK_START, BLOCK_END)
    return (
        _HARNESS % {"now": json.dumps(now), "block": json.dumps(block)}
        + "\n"
        + checks
    )


# ── structure ────────────────────────────────────────────────────────────────


def test_filter_block_exists_and_main_script_parses(tmp_path):
    assert BLOCK_START in SRC and BLOCK_END in SRC
    start = SRC.index("<script>") + len("<script>")
    end = SRC.index("</script>", start)
    f = tmp_path / "main.js"
    f.write_text(SRC[start:end], encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--check", str(f)], capture_output=True, text=True, timeout=30, check=False
    )
    assert proc.returncode == 0, proc.stderr[-1500:]


def test_rgn_btn_groups_have_handlers_wired_at_boot():
    block = _slice(BLOCK_START, BLOCK_END)
    # Groups are selected by the container ids that exist in the markup...
    assert 'id="regionPresets"' in SRC and 'id="timeFilter"' in SRC
    assert "#regionPresets" in block and "#timeFilter" in block
    assert "addEventListener('click'" in block
    # ...and matched by data attributes, never by the (translated) label.
    assert "data-region" in block and "data-hours" in block
    assert "textContent" not in block and "innerText" not in block
    # Wired once the map exists.
    boot = SRC[SRC.index("// ════════════ BOOT ════════════"):]
    assert boot.index("initMap();") < boot.index("_initFilters();")


def test_markup_ships_aria_pressed_and_default_state():
    for attr, default in (("data-region", "global"), ("data-hours", "24")):
        tags = re.findall(r"<button\b[^>]*\b%s=\"[^\"]*\"[^>]*>" % attr, SRC)
        assert tags, attr
        for tag in tags:
            val = re.search(r'%s="([^"]*)"' % attr, tag).group(1)
            on = val == default
            assert ('aria-pressed="%s"' % ("true" if on else "false")) in tag, tag
            assert ("active" in tag) == on, tag


def test_region_and_hours_values_match_the_markup():
    block = _slice(BLOCK_START, BLOCK_END)
    regions = set(re.findall(r'data-region="(\w+)"', SRC))
    hours = set(re.findall(r'data-hours="(\d+)"', SRC))
    assert regions == {"global", "americas", "europe", "mena", "asia", "africa"}
    assert hours == {"1", "6", "24", "168", "0"}
    for r in regions - {"global"}:
        assert re.search(r"\b%s\s*:\s*\[\[" % r, block), r


def test_applies_to_hint_is_translated_and_consistent():
    hint = "Applies to: Earthquakes, News, Conflict events"
    assert f'title="{hint}"' in SRC
    assert zh_TW.DASHBOARD[hint]
    # No tooltip may promise layers the filter does not touch.
    assert zh_TW.DASHBOARD[hint] == zh_TW.MESSAGES[hint]


# ── region buttons ───────────────────────────────────────────────────────────


def test_region_click_fits_bounds_and_toggles_active(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
const europe = regionBtns[2];
europe.click();
const snap1 = {
    calls: calls.map((c) => ({ fn: c.fn, b: c.b, animate: c.o && c.o.animate })),
    active: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    pressed: regionBtns.map((b) => b.getAttribute('aria-pressed')),
    stored: store['phoenix-region'],
};
calls.length = 0;
regionBtns[0].click();   // back to the globe
const snap2 = {
    calls: calls.map((c) => ({ fn: c.fn, c: c.c, z: c.z })),
    active: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    stored: store['phoenix-region'],
};
console.log(JSON.stringify({ snap1, snap2 }));
"""))
    s1, s2 = out["snap1"], out["snap2"]
    assert s1["calls"] == [{"fn": "fitBounds", "b": [[34, -25], [72, 45]], "animate": True}]
    assert s1["active"] == ["europe"]
    assert s1["pressed"] == ["false", "false", "true", "false", "false", "false"]
    assert s1["stored"] == "europe"
    assert s2["calls"] == [{"fn": "setView", "c": [20, 0], "z": 2.5}]
    assert s2["active"] == ["global"]
    assert s2["stored"] == "global"


def test_every_region_uses_its_own_bounds(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
const seen = {};
regionBtns.slice(1).forEach((b) => { calls.length = 0; b.click(); seen[b.getAttribute('data-region')] = calls[0].b; });
console.log(JSON.stringify(seen));
"""))
    for name, ((s, w), (n, e)) in out.items():
        assert -90 <= s < n <= 90 and -180 <= w < e <= 180, name
    assert len({json.dumps(v) for v in out.values()}) == 5


def test_region_click_ignores_the_label_text(tmp_path):
    """The translator rewrote the labels to Chinese; routing must not care."""
    out = _run(tmp_path, _script("""
load(); _initFilters();
regionBtns[3].textContent = '完全不相干的文字';
regionBtns[3].click();
console.log(JSON.stringify({ b: calls[0].b, a: regionBtns[3].active() }));
"""))
    assert out["b"] == [[12, -18], [42, 63]]
    assert out["a"] is True


def test_region_padding_keeps_content_out_from_under_the_panels(tmp_path):
    out = _run(tmp_path, _script("""
global.document = { getElementById: (id) => ({
    layers: { getBoundingClientRect: () => ({ right: 220, bottom: 600 }) },
    topBar: { getBoundingClientRect: () => ({ bottom: 56 }) },
    ticker: { getBoundingClientRect: () => ({ top: 866 }) },
    drawer: { classList: { contains: (c) => c === 'closed' }, getBoundingClientRect: () => ({ left: 1100 }) },
})[id] || null };
load(); _initFilters();
regionBtns[1].click();
console.log(JSON.stringify(calls[0].o));
"""))
    assert out["paddingTopLeft"][0] >= 220 and out["paddingTopLeft"][1] >= 56
    assert out["paddingBottomRight"][1] >= 34
    # Closed drawer must not eat horizontal room.
    assert out["paddingBottomRight"][0] < 100


# ── time-window buttons ──────────────────────────────────────────────────────


def test_time_click_updates_window_and_redraws_from_latest_data(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
latestData = { earthquakes: { earthquakes: [] }, news_feed: { articles: [] },
               acled_events: { count: 3, events: [{}] }, ucdp_events: {}, conflict_zones: {} };
hourBtns[0].click();   // 1h
console.log(JSON.stringify({
    active: hourBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-hours')),
    pressed: hourBtns.map((b) => b.getAttribute('aria-pressed')),
    stored: store['phoenix-hours'],
    redraw: redraws.map((r) => r.fn),
    quakesArg: redraws.find((r) => r.fn === 'updateMapQuakes').arg === latestData.earthquakes,
    newsArg: redraws.find((r) => r.fn === 'updateMapNews').arg === latestData.news_feed,
    conflictArg: redraws.find((r) => r.fn === 'updateMapConflict').arg === latestData.acled_events,
    hudArg: redraws.find((r) => r.fn === 'updateHudStats').arg === latestData,
    forbidden,
    mapCalls: calls.length,
}));
"""))
    assert out["active"] == ["1"]
    assert out["pressed"] == ["true", "false", "false", "false", "false"]
    assert out["stored"] == "1"
    assert set(out["redraw"]) == {
        "updateMapQuakes", "updateMapConflict", "updateMapNews", "updateHudStats", "updateTicker",
    }
    assert out["quakesArg"] and out["newsArg"] and out["conflictArg"] and out["hudArg"]
    assert out["forbidden"] == []
    assert out["mapCalls"] == 0  # a time filter never moves the map


def test_time_click_before_first_data_does_not_throw(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
hourBtns[4].click();
console.log(JSON.stringify({ redraws: redraws.length, active: hourBtns[4].active() }));
"""))
    assert out == {"redraws": 0, "active": True}


def test_time_click_ignores_the_label_text(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
hourBtns[1].textContent = '六小時';   // translated / arbitrary
hourBtns[1].click();
console.log(JSON.stringify({ stored: store['phoenix-hours'],
    in5h: _withinTimeWindow(new Date(NOW - 5 * 3600e3).toISOString()),
    in7h: _withinTimeWindow(new Date(NOW - 7 * 3600e3).toISOString()) }));
"""))
    assert out == {"stored": "6", "in5h": True, "in7h": False}


# ── _withinTimeWindow ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "hours, inside_s, outside_s",
    [(1, 3600 - 1, 3600 + 1), (6, 6 * 3600 - 1, 6 * 3600 + 1),
     (24, 86400 - 1, 86400 + 1), (168, 168 * 3600 - 1, 168 * 3600 + 1)],
)
def test_within_time_window_edges(tmp_path, hours, inside_s, outside_s):
    out = _run(tmp_path, _script(f"""
store['phoenix-hours'] = '{hours}';
load();
const iso = (s) => new Date(NOW - s * 1000).toISOString();
console.log(JSON.stringify({{
    inside: _withinTimeWindow(iso({inside_s})),
    outside: _withinTimeWindow(iso({outside_s})),
    future: _withinTimeWindow(new Date(NOW + 60e3).toISOString()),
}}));
"""))
    assert out == {"inside": True, "outside": False, "future": True}


def test_all_window_keeps_everything(tmp_path):
    out = _run(tmp_path, _script("""
store['phoenix-hours'] = '0';
load();
console.log(JSON.stringify({ old: _withinTimeWindow('2001-01-01T00:00:00Z'),
                             ancient: _withinTimeWindow('1970-01-02') }));
"""))
    assert out == {"old": True, "ancient": True}


def test_missing_or_unparseable_timestamps_stay_in_range(tmp_path):
    """No timestamp (or one we cannot read) must never silently drop data."""
    out = _run(tmp_path, _script("""
store['phoenix-hours'] = '1';
load();
console.log(JSON.stringify([undefined, null, '', 'not a date', '2026-13-99', {}].map(_withinTimeWindow)));
"""))
    assert out == [True] * 6


def test_date_only_timestamps_count_as_end_of_that_utc_day(tmp_path):
    """ACLED/UCDP carry day-granular dates; treating them as 00:00 would drop
    today's events from every window shorter than the time since midnight."""
    out = _run(tmp_path, _script("""
const check = (h, d) => { store['phoenix-hours'] = String(h); load(); return _withinTimeWindow(d); };
console.log(JSON.stringify({
    today_1h: check(1, '2026-10-11'),
    yesterday_6h: check(6, '2026-10-10'),
    yesterday_24h: check(24, '2026-10-10'),
    ucdp_midnight_24h: check(24, '2026-10-10T00:00:00.000'),
    ucdp_midnight_6h: check(6, '2026-10-10T00:00:00.000'),
    three_days_24h: check(24, '2026-10-08'),
    three_days_168h: check(168, '2026-10-08'),
}));
"""))
    assert out == {
        "today_1h": True,
        "yesterday_6h": False,
        "yesterday_24h": True,
        "ucdp_midnight_24h": True,
        "ucdp_midnight_6h": False,
        "three_days_24h": False,
        "three_days_168h": True,
    }


# ── persistence ──────────────────────────────────────────────────────────────


def test_saved_choices_are_restored_and_applied(tmp_path):
    out = _run(tmp_path, _script("""
store['phoenix-region'] = 'africa';
store['phoenix-hours'] = '168';
load(); _initFilters();
console.log(JSON.stringify({
    regionActive: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    hoursActive: hourBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-hours')),
    hoursPressed: hourBtns.map((b) => b.getAttribute('aria-pressed')),
    calls: calls.map((c) => ({ fn: c.fn, b: c.b, animate: c.o && c.o.animate })),
    in3d: _withinTimeWindow(new Date(NOW - 3 * 86400e3).toISOString()),
    in8d: _withinTimeWindow(new Date(NOW - 8 * 86400e3).toISOString()),
}));
"""))
    assert out["regionActive"] == ["africa"]
    assert out["hoursActive"] == ["168"]
    assert out["hoursPressed"] == ["false", "false", "false", "true", "false"]
    assert out["calls"] == [{"fn": "fitBounds", "b": [[-35, -20], [38, 52]], "animate": False}]
    assert out["in3d"] is True and out["in8d"] is False


def test_defaults_when_nothing_saved(tmp_path):
    out = _run(tmp_path, _script("""
load(); _initFilters();
console.log(JSON.stringify({
    calls: calls.length,
    region: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    hours: hourBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-hours')),
    in20h: _withinTimeWindow(new Date(NOW - 20 * 3600e3).toISOString()),
    in30h: _withinTimeWindow(new Date(NOW - 30 * 3600e3).toISOString()),
}));
"""))
    assert out == {"calls": 0, "region": ["global"], "hours": ["24"], "in20h": True, "in30h": False}


@pytest.mark.parametrize("junk", ["", "abc", "5", "-1", "null", "1e3"])
def test_garbage_saved_values_fall_back_to_defaults(tmp_path, junk):
    out = _run(tmp_path, _script(f"""
store['phoenix-region'] = {json.dumps(junk)};
store['phoenix-hours'] = {json.dumps(junk)};
load(); _initFilters();
console.log(JSON.stringify({{
    calls: calls.length,
    region: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    hours: hourBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-hours')),
}}));
"""))
    assert out == {"calls": 0, "region": ["global"], "hours": ["24"]}


def test_unavailable_local_storage_never_throws(tmp_path):
    out = _run(tmp_path, _script("""
breakStorage();
load(); _initFilters();
regionBtns[2].click();
hourBtns[0].click();
console.log(JSON.stringify({
    region: regionBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-region')),
    hours: hourBtns.filter((b) => b.active()).map((b) => b.getAttribute('data-hours')),
    fit: calls.length,
}));
"""))
    # Still works in-session; just nothing persisted.
    assert out == {"region": ["europe"], "hours": ["1"], "fit": 1}


# ── the layers that consume the window ───────────────────────────────────────

_CONSUMERS = r"""
const mapLayers = {};
function Layer() { this.items = []; }
Layer.prototype.clearLayers = function () { this.items = []; };
Layer.prototype.getLayers = function () { return this.items; };
['quakes', 'conflict', 'news'].forEach((k) => { mapLayers[k] = new Layer(); global.mapLayers = mapLayers; });
const text = {};
global.$ = (sel) => ({ set textContent(v) { text[sel] = String(v); }, get textContent() { return text[sel]; },
                       set innerHTML(v) { text[sel] = String(v); }, style: { setProperty() {} } });
global.L = {
    divIcon: (o) => o,
    marker: () => { const m = { bindTooltip() { return m; }, on() { return m; },
        addTo(layer) { layer.items.push(m); return m; } }; return m; },
};
global.trunc = (s) => s; global._t = (s) => s; global.esc = (s) => s; global.safe = (s) => s;
global.showDetail = () => {};
global._geolocateArticle = (a) => (a.nogeo ? null : { country: 'x', lat: 10, lon: 10 });
global.latestData = null;
global.COUNTRY_CENTROIDS = {};
const FNS = %(fns)s;
vm.runInThisContext(FNS);
vm.runInThisContext(BLOCK);
"""


def _consumer_script(checks: str) -> str:
    fns = "\n".join(
        [
            _slice("function updateMapQuakes(", "function updateMapMilitary("),
            _slice("function updateMapConflict(", "function updateMapFires("),
            _slice("function updateMapNews(", "function updateAlertBanner("),
            _slice("function updateHudStats(", "// ════════════ DATA DRAWER ════════════"),
            _slice("function updateTicker(", "// ════════════ MASTER UPDATE ════════════"),
        ]
    )
    block = _slice(BLOCK_START, BLOCK_END)
    # Helpers shared by the consumers live right next to the block.
    return (
        _HARNESS % {"now": json.dumps(NOW), "block": json.dumps(block)}
        + "\n"
        + _CONSUMERS % {"fns": json.dumps(fns)}
        + "\n"
        + checks
    )


def _iso_ago(hours: float) -> str:
    from datetime import datetime, timedelta, timezone

    now = datetime(2026, 10, 11, 12, 0, 0, tzinfo=timezone.utc)
    return (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dataset() -> dict:
    return {
        "earthquakes": {
            "earthquakes": [
                {"latitude": 1, "longitude": 1, "magnitude": 5, "time": _iso_ago(0.5)},
                {"latitude": 2, "longitude": 2, "magnitude": 5, "time": _iso_ago(5)},
                {"latitude": 3, "longitude": 3, "magnitude": 5, "time": _iso_ago(23)},
                {"latitude": 4, "longitude": 4, "magnitude": 5, "time": _iso_ago(72)},
                {"latitude": 5, "longitude": 5, "magnitude": 5, "time": _iso_ago(24 * 30)},
            ]
        },
        "news_feed": {
            "articles": [
                {"title": "a", "published": _iso_ago(0.2)},
                {"title": "b", "published": _iso_ago(4)},
                {"title": "c", "published": _iso_ago(20)},
                {"title": "d", "published": _iso_ago(100)},
                {"title": "e", "published": _iso_ago(24 * 20)},
                {"title": "f", "published": _iso_ago(2), "nogeo": True},
            ]
        },
        "acled_events": {
            "count": 5,
            "events": [
                {"latitude": 1, "longitude": 1, "event_date": "2026-10-11"},
                {"latitude": 2, "longitude": 2, "event_date": "2026-10-10"},
                {"latitude": 3, "longitude": 3, "event_date": "2026-10-08"},
                {"latitude": 4, "longitude": 4, "event_date": "2026-09-01"},
                {"latitude": 5, "longitude": 5},
            ],
        },
    }


_SWEEP = """
const data = %s;
const out = {};
for (const h of [1, 6, 24, 168, 0]) {
    store['phoenix-hours'] = String(h);
    vm.runInThisContext(BLOCK);
    updateMapQuakes(data.earthquakes);
    updateMapConflict(_conflictSource(data));
    updateMapNews(data.news_feed);
    updateHudStats(data);
    updateTicker(data);
    const hud = text['#hudStats'];
    out[h] = {
        quakes: text['#cntQuakes'], conflict: text['#cntConflict'], news: text['#cntNews'],
        quakeMarkers: mapLayers.quakes.items.length,
        conflictMarkers: mapLayers.conflict.items.length,
        newsMarkers: mapLayers.news.items.length,
        hudQuakes: (hud.match(/data-layer="quakes"><span class="v">(\\d+)/) || [])[1],
        hudConflict: (hud.match(/data-layer="conflict"><span class="v[^"]*">(\\d+)/) || [])[1],
        tickerItems: (text['#tickerContent'].match(/ticker-item">/g) || []).length,
    };
}
console.log(JSON.stringify(out));
"""


def test_quake_conflict_news_counts_follow_the_window(tmp_path):
    out = _run(tmp_path, _consumer_script(_SWEEP % json.dumps(_dataset())))
    quakes = {h: int(v["quakes"]) for h, v in out.items()}
    assert quakes == {"1": 1, "6": 2, "24": 3, "168": 4, "0": 5}
    # Markers on the map match the sidebar count (all under the 100 cap).
    assert {h: v["quakeMarkers"] for h, v in out.items()} == quakes
    # Conflict: today / yesterday / 3 days / 6 weeks / undated.  Undated stays.
    conflict = {h: int(v["conflict"]) for h, v in out.items()}
    assert conflict == {"1": 2, "6": 2, "24": 3, "168": 4, "0": 5}
    assert {h: v["conflictMarkers"] for h, v in out.items()} == conflict
    # News counts geolocated articles that fall inside the window.
    news = {h: int(v["news"]) for h, v in out.items()}
    assert news == {"1": 1, "6": 2, "24": 3, "168": 4, "0": 5}
    assert {h: v["newsMarkers"] for h, v in out.items()} == news


def test_hud_pills_and_ticker_agree_with_the_layers(tmp_path):
    out = _run(tmp_path, _consumer_script(_SWEEP % json.dumps(_dataset())))
    assert {h: int(v["hudQuakes"]) for h, v in out.items()} == {
        "1": 1, "6": 2, "24": 3, "168": 4, "0": 5}
    assert {h: int(v["hudConflict"]) for h, v in out.items()} == {
        "1": 2, "6": 2, "24": 3, "168": 4, "0": 5}
    # Ticker shows headlines, geolocated or not: a(0.2) b(4) f(2) c(20) d(100)
    # e(480).  The scroller renders the list twice for a seamless loop.
    assert {h: v["tickerItems"] // 2 for h, v in out.items()} == {
        "1": 1, "6": 3, "24": 4, "168": 5, "0": 6}


def test_all_window_keeps_the_unfiltered_conflict_total(tmp_path):
    """With nothing filtered out the layer keeps showing the server's count
    (which can exceed the events actually returned)."""
    data = _dataset()
    data["acled_events"]["count"] = 480
    out = _run(tmp_path, _consumer_script(_SWEEP % json.dumps(data)))
    assert out["0"]["conflict"] == "480"
    assert out["24"]["conflict"] == "3"


def test_geolocated_news_marker_does_not_hop_on_redraw(tmp_path):
    out = _run(tmp_path, _consumer_script("""
const feed = { articles: [{ title: 'a', published: '%s' }] };
global.Math.random = () => 0.9;
updateMapNews(feed);
const first = [feed.articles[0]._geo_lat, feed.articles[0]._geo_lon];
global.Math.random = () => 0.1;
updateMapNews(feed);
console.log(JSON.stringify({ first, second: [feed.articles[0]._geo_lat, feed.articles[0]._geo_lon] }));
""" % _iso_ago(1)))
    assert out["first"] == out["second"]
