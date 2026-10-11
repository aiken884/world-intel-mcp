"""HUD stat-pill click-to-zoom needs layers that implement ``getBounds()``.

``L.layerGroup()`` has no ``getBounds()`` (only ``L.featureGroup()`` and the
marker-cluster group do), so the pill handler's ``try/catch`` swallowed a
TypeError and the click silently did not zoom.  These tests cross-check the
layer a pill points at against the constructor that built it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from world_intel_mcp import i18n

INDEX_HTML = Path(i18n.__file__).parent / "dashboard" / "index.html"
SRC = INDEX_HTML.read_text(encoding="utf-8")

# Constructors whose result exposes getBounds().
BOUNDS_CAPABLE = {"featureGroup", "markerClusterGroup"}


def _pill_layers() -> set[str]:
    return set(re.findall(r'class="stat-pill"\s+data-layer="(\w+)"', SRC))


def _layer_constructors() -> dict[str, str]:
    return dict(re.findall(r"mapLayers\.(\w+)\s*=\s*L\.(\w+)\(", SRC))


def test_pill_layers_were_discovered():
    # Guard: a regex that matches nothing would make the next test vacuous.
    assert {"quakes", "military", "conflict", "fires", "nuclear",
            "exposure", "airtraffic", "traffic", "webcams"} <= _pill_layers()


def test_every_hud_pill_layer_supports_get_bounds():
    ctors = _layer_constructors()
    bad = {k: ctors.get(k) for k in sorted(_pill_layers()) if ctors.get(k) not in BOUNDS_CAPABLE}
    assert not bad, f"pill layers built without getBounds(): {bad}"


def test_pill_click_handler_still_guards_with_is_valid():
    start = SRC.index("$('#hudStats').addEventListener('click'")
    end = SRC.index("// Search", start)
    handler = SRC[start:end]
    assert "getBounds()" in handler
    assert "bounds.isValid()" in handler
    assert "fitBounds(" in handler


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_main_inline_script_parses(tmp_path):
    start = SRC.index("<script>") + len("<script>")
    end = SRC.index("</script>", start)
    f = tmp_path / "main.js"
    f.write_text(SRC[start:end], encoding="utf-8")
    proc = subprocess.run(
        [shutil.which("node"), "--check", str(f)], capture_output=True, text=True, timeout=30, check=False
    )
    assert proc.returncode == 0, proc.stderr[-1500:]
