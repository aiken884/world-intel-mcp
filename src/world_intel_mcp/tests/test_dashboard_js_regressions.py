"""Regression tests for dashboard JS that runs after the zh-TW DOM translator.

The dashboard is a single static HTML file with no JS test harness, so these
tests slice the relevant snippets out of ``index.html`` and run them under
``node`` against a minimal fake DOM.  What is asserted is observable behaviour
(write counts, which layer a click resolves to, what is persisted), not that
the file merely parses.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from world_intel_mcp import i18n

INDEX_HTML = Path(i18n.__file__).parent / "dashboard" / "index.html"
NODE = shutil.which("node")

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _slice(start: str, end: str) -> str:
    """Return the JS between two marker strings (start inclusive, end exclusive)."""
    src = INDEX_HTML.read_text(encoding="utf-8")
    i = src.index(start)
    j = src.index(end, i)
    return src[i:j]


def _run(tmp_path: Path, script: str) -> dict:
    f = tmp_path / "case.js"
    f.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [NODE, str(f)], capture_output=True, text=True, timeout=30, check=False
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


# ── fake DOM for the MutationObserver based translator ──────────────────────

_FAKE_DOM = r"""
const vm = require('vm');
const records = [];
const rafQueue = [];
let observerCb = null;
global.requestAnimationFrame = function (f) { rafQueue.push(f); return rafQueue.length; };
global.MutationObserver = function (cb) { observerCb = cb; this.observe = function () {}; };

function Text(v) { this.nodeType = 3; this._v = v; this.writes = 0; this.nextSibling = null; this.firstChild = null; }
Object.defineProperty(Text.prototype, 'nodeValue', {
    get() { return this._v; },
    // Like a real DOM: assigning even an identical value queues a record.
    set(x) { this._v = x; this.writes++; records.push({ type: 'characterData', target: this }); },
});
function El(tag, attrs, kids) {
    this.nodeType = 1; this.tagName = tag; this.className = '';
    this._a = Object.assign({}, attrs || {}); this.attrWrites = 0;
    this.firstChild = null; this.nextSibling = null;
    let prev = null;
    (kids || []).forEach((k) => { if (prev) prev.nextSibling = k; else this.firstChild = k; prev = k; });
}
El.prototype.getAttribute = function (a) { return Object.prototype.hasOwnProperty.call(this._a, a) ? this._a[a] : null; };
El.prototype.setAttribute = function (a, v) {
    this._a[a] = String(v); this.attrWrites++;
    records.push({ type: 'attributes', target: this, attributeName: a });
};

// Deliver records -> rAF flush, until quiet or maxRounds is hit.
function settle(maxRounds) {
    let rounds = 0;
    // records.length > 2000: runaway feedback loop (bail out instead of OOM).
    while (rounds < maxRounds && records.length <= 2000 && (records.length || rafQueue.length)) {
        if (records.length) observerCb(records.splice(0));
        rafQueue.splice(0).forEach((f) => f());
        rounds++;
    }
    return rounds;
}
function boot(i18n, root) {
    global.window = { __I18N__: i18n };
    global.document = { documentElement: root };
    vm.runInThisContext(I18N_SRC);
}
"""


def _i18n_script(dictionary: dict, build_tree: str, checks: str) -> str:
    src = _slice("// ════════════ I18N ════════════", "// ════════════ STATE ════════════")
    return (
        f"const I18N_SRC = {json.dumps(src)};\n"
        + _FAKE_DOM
        + f"const DICT = {json.dumps(dictionary)};\n"
        + build_tree
        + "\nboot(DICT, root);\n"
        + checks
    )


IDENTITY = {"Kp": "Kp", "ID": "ID", "ETF": "ETF", "SMA-50": "SMA-50"}


def test_identity_entries_do_not_keep_the_observer_busy(tmp_path):
    """Entries whose translation equals the msgid must not be re-written.

    Re-assigning the same nodeValue/attribute still queues a mutation record,
    so the translator's own write re-triggered itself on every frame forever.
    """
    script = _i18n_script(
        {**IDENTITY, "Quakes": "地震"},
        """
const idText = new Text('Kp');
const paddedText = new Text('  ID  ');
const tr = new Text('Quakes');
const input = new El('INPUT', { placeholder: 'ETF', title: 'SMA-50' });
const root = new El('HTML', {}, [new El('SPAN', {}, [idText]), new El('SPAN', {}, [paddedText]),
                                  new El('SPAN', {}, [tr]), input]);
""",
        """
const rounds = settle(25);
// A node inserted later (Leaflet popup / panel redraw) must settle too.
const late = new Text('ETF');
const lateEl = new El('DIV', { title: 'Kp' }, [late]);
records.push({ type: 'childList', addedNodes: [lateEl] });
const rounds2 = settle(25);
console.log(JSON.stringify({
    rounds, rounds2, pending: records.length + rafQueue.length,
    idWrites: idText.writes, paddedWrites: paddedText.writes, lateWrites: late.writes,
    attrWrites: input.attrWrites, lateAttrWrites: lateEl.attrWrites,
    translated: tr._v, translatedWrites: tr.writes,
}));
""",
    )
    r = _run(tmp_path, script)
    assert r["pending"] == 0, f"observer never went quiet: {r}"
    assert r["rounds"] <= 5 and r["rounds2"] <= 5, r
    assert (r["idWrites"], r["paddedWrites"], r["lateWrites"]) == (0, 0, 0), r
    assert (r["attrWrites"], r["lateAttrWrites"]) == (0, 0), r
    # Real translations still apply, exactly once.
    assert r["translated"] == "地震" and r["translatedWrites"] == 1, r


def test_replacement_text_is_inserted_literally(tmp_path):
    """A translation containing ``$&`` / ``$1`` must not be treated as a pattern."""
    script = _i18n_script(
        {"Cost": "價格 $& ($1) $$", "Plain": "一般"},
        """
const a = new Text('  Cost ');
const b = new Text('Plain');
const root = new El('HTML', {}, [new El('SPAN', {}, [a]), new El('SPAN', {}, [b])]);
""",
        """
settle(25);
console.log(JSON.stringify({ a: a._v, b: b._v, pending: records.length + rafQueue.length }));
""",
    )
    r = _run(tmp_path, script)
    assert r["a"] == "  價格 $& ($1) $$ ", r
    assert r["b"] == "一般" and r["pending"] == 0, r


# ── HUD pill click-to-zoom ──────────────────────────────────────────────────


def test_hud_pill_click_resolves_layer_from_attribute_not_label_text(tmp_path):
    """Label text is translated ("地震"), so the layer key must come from data-layer."""
    handler = _slice("// HUD pill click-to-zoom", "// Search")
    script = (
        "const vm = require('vm');\n"
        f"const SRC = {json.dumps(handler)};\n"
        r"""
const listeners = {};
const fits = [];
const bounds = { isValid: () => true, getNorthEast: () => ({ lat: 2 }), getSouthWest: () => ({ lat: 1 }) };
global.mapLayers = { quakes: { getBounds: () => bounds, addTo() {} } };
global.layerState = { quakes: true };
global.map = { fitBounds: (b, o) => fits.push(o) };
global.document = { querySelector: () => null };
global.localStorage = { setItem() {} };
global.$ = (sel) => ({ addEventListener: (ev, fn) => { listeners[sel + ':' + ev] = fn; } });
vm.runInThisContext(SRC);

function click(layer, labelText) {
    const pill = {
        getAttribute: (a) => (a === 'data-layer' ? layer : null),
        querySelector: (s) => (s === '.l' ? { textContent: labelText } : null),
    };
    listeners['#hudStats:click']({ target: { closest: (s) => (s === '.stat-pill' ? pill : null) } });
}
click('quakes', '地震');      // zh-TW: translated label
const zh = fits.length;
click(null, 'Kp');            // pill without a layer: no-op
const none = fits.length;
console.log(JSON.stringify({ zh, none }));
"""
    )
    r = _run(tmp_path, script)
    assert r == {"zh": 1, "none": 1}, r


def test_hud_label_text_is_no_longer_used_as_a_lookup_key():
    src = INDEX_HTML.read_text(encoding="utf-8")
    assert "HUD_LAYER_MAP[label.textContent" not in src
    assert "HUD_LAYER_MAP" not in src


def test_hud_stat_pills_carry_their_layer_key(tmp_path):
    # The pills read the time window through the shared filter helpers.
    fn = _slice(
        "// ════════════ REGION & TIME FILTERS", "// ════════════ END REGION & TIME FILTERS"
    ) + _slice("function updateHudStats(data) {", "// ════════════ DATA DRAWER")
    script = (
        f"const SRC = {json.dumps(fn)};\n"
        r"""
const vm = require('vm');
let html = '';
global.$ = () => ({ set innerHTML(v) { html = v; } });
global.safe = (h) => h;
global.fmtBigPlain = (n) => String(n);
vm.runInThisContext(SRC);
updateHudStats({
  earthquakes: { earthquakes: [1, 2] }, military_flights: { count: 3 },
  acled_events: { count: 5 }, cyber_threats: { threats: [] },
  wildfires: { fires_by_region: { a: { top_clusters: [1] } } },
  displacement: { global_totals: { grand_total: 5 } }, space_weather: { current_kp: 3 },
  ai_watch: { count: 1 }, alert_digest: { alert_count: 2, by_priority: {} },
  shipping_index: { stress_score: 10 }, disease_outbreaks: { high_concern_count: 1 },
  nuclear_monitor: { critical_flags: 1 }, strategic_posture: { composite_score: 40 },
  population_exposure: { exposed_city_count: 1, total_exposed_population_formatted: '1M' },
  domestic_flights: { total_aircraft: 100 }, traffic_flow: { count: 1 }, webcams: { count: 2 },
});
console.log(JSON.stringify({ html }));
"""
    )
    html = _run(tmp_path, script)["html"]
    pills = re.findall(
        r'<div class="stat-pill"([^>]*)>.*?<span class="l">([^<]+)</span></div>', html
    )
    by_label = {label: attrs for attrs, label in pills}
    expected = {
        "Quakes": "quakes",
        "Aircraft": "military",
        "Conflict": "conflict",
        "Fires": "fires",
        "Exposed": "exposure",
        "Airborne": "airtraffic",
        "Traffic": "traffic",
        "Cams": "webcams",
        "Nuke Flag": "nuclear",
    }
    assert len(pills) >= 15, pills
    for label, layer in expected.items():
        assert f'data-layer="{layer}"' in by_label.get(label, ""), (label, by_label)


# ── drawer section collapse state ───────────────────────────────────────────


def test_drawer_section_headers_have_a_stable_key():
    src = INDEX_HTML.read_text(encoding="utf-8")
    headers = re.findall(r"""<div class="sh"[^>]*>[^<]*</div>""", src)
    assert len(headers) >= 20
    for h in headers:
        m = re.match(r'<div class="sh" data-sh="([^"]+)">([^<]*)</div>', h)
        assert m, f"section header lacks data-sh: {h}"
        assert m.group(1) == m.group(2), f"data-sh must be the English msgid: {h}"


def test_collapsed_drawer_sections_survive_a_redraw_after_translation(tmp_path):
    """Saved while translated (中文), restored while still English: must still match."""
    click_src = _slice("// Drawer click delegation", "// HUD pill click-to-zoom")
    restore_src = _slice(
        "// Restore collapsed drawer sections from localStorage", "// ════════════ NEWS TICKER"
    )
    # keep only the try{...} restore block (drop the closing brace of updateDrawer)
    restore_src = restore_src[: restore_src.rindex("}")]
    script = (
        "const vm = require('vm');\n"
        f"const CLICK = {json.dumps(click_src)};\n"
        f"const RESTORE = {json.dumps(restore_src)};\n"
        r"""
const store = {};
global.localStorage = { getItem: (k) => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = v; } };
const classes = (set) => ({
    add: (c) => set.add(c), remove: (c) => set.delete(c), contains: (c) => set.has(c),
    toggle(c) { if (set.has(c)) set.delete(c); else set.add(c); },
});
function section(key, shown) {
    const set = new Set(['sh']);
    const body = { classList: classes(new Set(['row'])), style: {}, nextElementSibling: null };
    const el = { classList: classes(set), textContent: shown, style: {}, nextElementSibling: body,
                 getAttribute: (a) => (a === 'data-sh' ? key : null), _set: set, _body: body };
    return el;
}
let current = [];
let listener = null;
global.$$ = (sel) => (sel === '#drawerBody .sh.collapsed' ? current.filter((s) => s._set.has('collapsed')) : current);
global.$ = (sel) => ({ addEventListener: (ev, fn) => { listener = fn; } });
vm.runInThisContext(CLICK);

// 1. translated drawer: user collapses ALERTS (displayed as 警示)
current = [section('STRATEGIC POSTURE', '戰略態勢'), section('ALERTS', '警示')];
listener({ target: { closest: (s) => (s === '.sh' ? current[1] : null) } });

// 2. the drawer is rebuilt; the observer has not translated yet -> English text
current = [section('STRATEGIC POSTURE', 'STRATEGIC POSTURE'), section('ALERTS', 'ALERTS')];
vm.runInThisContext(RESTORE);
console.log(JSON.stringify({
    saved: store['phoenix-drawer-collapsed'],
    postureCollapsed: current[0]._set.has('collapsed'),
    alertsCollapsed: current[1]._set.has('collapsed'),
    alertsBodyHidden: current[1]._body.style.display === 'none',
}));
"""
    )
    r = _run(tmp_path, script)
    assert json.loads(r["saved"]) == ["ALERTS"], r
    assert r["alertsCollapsed"] is True and r["alertsBodyHidden"] is True, r
    assert r["postureCollapsed"] is False, r


def test_dashboard_javascript_has_valid_syntax(tmp_path):
    src = INDEX_HTML.read_text(encoding="utf-8")
    scripts = re.findall(r"<script>(.*?)</script>", src, flags=re.S)
    assert scripts
    f = tmp_path / "main.js"
    f.write_text("\n".join(scripts), encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--check", str(f)], capture_output=True, text=True, timeout=30, check=False
    )
    assert proc.returncode == 0, proc.stderr[-1500:]


# ── external links inside the pywebview (macOS .app) window ─────────────────


def _link_interceptor_script(api_decl: str, href: str) -> str:
    """Run the global link interceptor under a fake document/window."""
    handler = _slice(
        "// ════════════ GLOBAL LINK INTERCEPTOR ════════════",
        "// ════════════ KEYBOARD SHORTCUTS ════════════",
    )
    return (
        "const vm = require('vm');\n"
        f"const SRC = {json.dumps(handler)};\n"
        + r"""
const calls = { api: [], open: [], prevented: 0, stopped: 0 };
let listener = null;
global.document = { addEventListener: (ev, fn) => { if (ev === 'click') listener = fn; } };
global.window = { open: (u, t, f) => calls.open.push([u, t, f]) };
"""
        + api_decl
        + "\nvm.runInThisContext(SRC);\n"
        + f"const HREF = {json.dumps(href)};\n"
        + r"""
const a = {
    getAttribute: (n) => (n === 'href' ? HREF : null),
    hasAttribute: (n) => false,
};
listener({
    target: { closest: (s) => (s === 'a[href]' ? a : null) },
    preventDefault: () => { calls.prevented++; },
    stopPropagation: () => { calls.stopped++; },
});
console.log(JSON.stringify(calls));
"""
    )


def test_external_link_uses_pywebview_api_when_present(tmp_path):
    api = "global.window.pywebview = { api: { open_url: (u) => calls.api.push(u) } };"
    r = _run(tmp_path, _link_interceptor_script(api, "https://example.com/x"))
    assert r["api"] == ["https://example.com/x"], r
    assert r["open"] == [], r
    assert r["prevented"] == 1, r


def test_external_link_falls_back_to_window_open_in_a_normal_browser(tmp_path):
    r = _run(tmp_path, _link_interceptor_script("", "https://example.com/x"))
    assert r["api"] == [], r
    assert r["open"] == [["https://example.com/x", "_blank", "noopener,noreferrer"]], r
    assert r["prevented"] == 1, r


def test_external_link_falls_back_when_pywebview_api_is_not_ready(tmp_path):
    # pywebview injects window.pywebview before the api methods are bound.
    r = _run(tmp_path, _link_interceptor_script("global.window.pywebview = {};", "http://example.com"))
    assert r["api"] == [] and len(r["open"]) == 1, r


def test_internal_anchor_is_left_alone(tmp_path):
    api = "global.window.pywebview = { api: { open_url: (u) => calls.api.push(u) } };"
    r = _run(tmp_path, _link_interceptor_script(api, "#section"))
    assert r["api"] == [] and r["open"] == [] and r["prevented"] == 0, r
