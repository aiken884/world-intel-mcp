"""Helpers of scripts/build-macos-app.sh and scripts/make-dmg.sh.

Both scripts are guarded (``BASH_SOURCE == $0``) so they can be sourced and
their small functions exercised without running a PyInstaller build.
"""

from __future__ import annotations

import plistlib
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BUILD_APP = ROOT / "scripts" / "build-macos-app.sh"
MAKE_DMG = ROOT / "scripts" / "make-dmg.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None or not BUILD_APP.exists() or not MAKE_DMG.exists(),
    reason="bash or scripts unavailable",
)


def _call(script: Path, snippet: str, cwd: Path) -> subprocess.CompletedProcess:
    prog = f'set -euo pipefail; source "{script}"; {snippet}'
    return subprocess.run(
        [BASH, "-c", prog], cwd=cwd, capture_output=True, text=True, timeout=30, check=False
    )


def test_project_version_reads_the_project_table(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.2.3"\n\n[tool.other]\nversion = "9.9.9"\n'
    )
    for script in (BUILD_APP, MAKE_DMG):
        r = _call(script, f'project_version "{tmp_path}/pyproject.toml"', tmp_path)
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip() == "1.2.3"


def test_repo_version_matches_pyproject():
    r = _call(MAKE_DMG, f'project_version "{ROOT}/pyproject.toml"', ROOT)
    import tomllib

    expected = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert r.stdout.strip() == expected


def test_dmg_name_embeds_version_and_arch(tmp_path):
    r = _call(MAKE_DMG, "dmg_name 0.10.0 arm64", tmp_path)
    assert r.stdout.strip() == "World-Intel-0.10.0-arm64.dmg"


@pytest.mark.skipif(shutil.which("plutil") is None, reason="plutil is macOS only")
def test_patch_info_plist_sets_the_required_keys(tmp_path):
    plist = tmp_path / "Info.plist"
    plist.write_bytes(plistlib.dumps({"CFBundleName": "World Intel", "CFBundleVersion": "0.0.0"}))
    r = _call(BUILD_APP, f'patch_info_plist "{plist}" 4.5.6', tmp_path)
    assert r.returncode == 0, r.stderr
    info = plistlib.loads(plist.read_bytes())
    assert info["CFBundleShortVersionString"] == "4.5.6"
    assert info["CFBundleVersion"] == "4.5.6"
    assert info["NSHighResolutionCapable"] is True
    assert info["NSAppTransportSecurity"] == {"NSAllowsLocalNetworking": True}
    assert info["LSMinimumSystemVersion"] == "12.0"
    assert info["CFBundleName"] == "World Intel"  # untouched keys survive


def test_app_build_never_deletes_the_cli_build():
    src = BUILD_APP.read_text(encoding="utf-8")
    assert 'rm -rf "$ROOT/dist"' not in src
    assert "dist/world-intel" in src  # mentioned only as "left alone"
    assert "rm -rf \"$WORK\" \"$APP\"" in src
