"""Basemap regression tests for the dashboard.

The CARTO ``dark_all`` tile service started answering every tile request with
the same "API KEY REQUIRED" watermark image, so the map was unreadable.  The
dashboard now uses the keyless OpenStreetMap standard tiles.  These tests pin
that choice (structure of ``index.html``) and the behaviour of the attribution
link handler (node + fake DOM, same approach as
``test_dashboard_js_regressions.py``).
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


def _src() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def _css_rule(selector: str) -> str:
    """Return the declaration block of the first rule whose selector is exactly ``selector``."""
    m = re.search(r"(?:^|\})\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", _src(), flags=re.M)
    assert m, f"CSS rule {selector!r} not found"
    return m.group(1)


# ── structure ───────────────────────────────────────────────────────────────


def test_no_carto_tile_service_is_referenced():
    src = _src()
    assert "cartocdn" not in src
    assert "basemaps." not in src


def test_tile_layer_is_openstreetmap_standard_tiles():
    src = _src()
    m = re.search(r"L\.tileLayer\(\s*'([^']+)'", src)
    assert m, "no L.tileLayer call found"
    assert m.group(1) == "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
    # OSM standard tiles stop at zoom 19.
    assert re.search(r"tile\.openstreetmap\.org/\{z\}/\{x\}/\{y\}\.png'\s*,\s*\{[^}]*maxZoom:\s*19", src)


def test_attribution_is_visible_and_credits_openstreetmap():
    src = _src()
    # OSM tile policy requires a visible credit: the control must not be disabled.
    assert not re.search(r"attributionControl\s*:\s*false", src)
    assert "openstreetmap.org/copyright" in src
    assert "OpenStreetMap" in src
    # No Leaflet advertising prefix.
    assert re.search(r"attributionControl\s*:\s*true", src)
    assert re.search(r"attributionControl\.setPrefix\(\s*false\s*\)", src)


def test_dark_theme_filter_applies_to_tile_pane_only():
    rule = _css_rule(".leaflet-tile-pane")
    assert "filter" in rule and "invert(1)" in rule, rule
    # Markers/clusters/lines live in other panes; the filter must not leak there.
    for pane in (".leaflet-marker-pane", ".leaflet-overlay-pane", ".leaflet-container"):
        for m in re.finditer(re.escape(pane) + r"\s*\{([^}]*)\}", _src()):
            assert "invert(" not in m.group(1), (pane, m.group(1))


def test_map_container_has_dark_background_so_missing_tiles_are_not_white():
    rule = _css_rule("#map")
    assert re.search(r"background(-color)?\s*:\s*#[0-9a-fA-F]{3,8}", rule), rule


def test_attribution_is_not_hidden_behind_the_ticker():
    rule = _css_rule(".leaflet-control-attribution")
    # Ticker is 34px tall and sits above the map stacking context.
    m = re.search(r"margin-bottom\s*:\s*(\d+)px", rule)
    assert m and int(m.group(1)) >= 34, rule


# ── attribution link handler ────────────────────────────────────────────────


def _handler_script(api_decl: str, closest_matches: bool, href: str = "https://www.openstreetmap.org/copyright") -> str:
    src = _src()
    start = "// ════════════ MAP ATTRIBUTION LINKS ════════════"
    end = "// ════════════ GLOBAL LINK INTERCEPTOR ════════════"
    handler = src[src.index(start) : src.index(end)]
    return (
        "const vm = require('vm');\n"
        f"const SRC = {json.dumps(handler)};\n"
        f"const HREF = {json.dumps(href)};\n"
        f"const MATCH = {json.dumps(closest_matches)};\n"
        + r"""
const calls = { api: [], open: [], prevented: 0, stopped: 0, selectors: [] };
const listeners = [];
global.document = { addEventListener: (ev, fn) => { if (ev === 'click') listeners.push(fn); } };
global.window = { open: (u, t, f) => calls.open.push([u, t, f]) };
"""
        + api_decl
        + "\nvm.runInThisContext(SRC);\n"
        + r"""
const a = { getAttribute: (n) => (n === 'href' ? HREF : null) };
listeners.forEach((fn) => fn({
    target: { closest: (s) => { calls.selectors.push(s); return MATCH && /leaflet-control-attribution/.test(s) ? a : null; } },
    preventDefault: () => { calls.prevented++; },
    stopPropagation: () => { calls.stopped++; },
}));
calls.listeners = listeners.length;
console.log(JSON.stringify(calls));
"""
    )


def _run(tmp_path: Path, script: str) -> dict:
    f = tmp_path / "case.js"
    f.write_text(script, encoding="utf-8")
    proc = subprocess.run([NODE, str(f)], capture_output=True, text=True, timeout=30, check=False)
    assert proc.returncode == 0, proc.stderr[-2000:]
    return json.loads(proc.stdout.strip().splitlines()[-1])


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_attribution_link_opens_via_pywebview_api_and_does_not_navigate(tmp_path):
    api = "global.window.pywebview = { api: { open_url: (u) => calls.api.push(u) } };"
    r = _run(tmp_path, _handler_script(api, True))
    assert r["listeners"] == 1, r
    assert r["api"] == ["https://www.openstreetmap.org/copyright"], r
    assert r["open"] == [], r
    assert r["prevented"] == 1, r
    assert any("leaflet-control-attribution" in s for s in r["selectors"]), r


@needs_node
def test_attribution_link_falls_back_to_window_open_in_a_browser(tmp_path):
    r = _run(tmp_path, _handler_script("", True))
    assert r["api"] == [], r
    assert r["open"] == [["https://www.openstreetmap.org/copyright", "_blank", "noopener"]], r
    assert r["prevented"] == 1, r


@needs_node
def test_attribution_link_falls_back_when_pywebview_api_is_not_ready(tmp_path):
    r = _run(tmp_path, _handler_script("global.window.pywebview = {};", True))
    assert r["api"] == [] and len(r["open"]) == 1, r


@needs_node
def test_clicks_outside_the_attribution_control_are_left_alone(tmp_path):
    api = "global.window.pywebview = { api: { open_url: (u) => calls.api.push(u) } };"
    r = _run(tmp_path, _handler_script(api, False))
    assert r["api"] == [] and r["open"] == [] and r["prevented"] == 0, r
