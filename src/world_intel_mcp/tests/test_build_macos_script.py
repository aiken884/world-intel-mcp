"""scripts/build-macos.sh must not destroy the user's API keys on rebuild.

The frozen executables read ``dist/world-intel/.env``; the build wipes
``dist/``.  The script exposes backup/restore helpers (sourceable, guarded by
a ``BASH_SOURCE == $0`` check) so this can be tested without running a build.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "build-macos.sh"
BASH = shutil.which("bash")

pytestmark = pytest.mark.skipif(
    BASH is None or not SCRIPT.exists(), reason="bash or build script unavailable"
)


def _call(snippet: str, cwd: Path) -> subprocess.CompletedProcess:
    # `set -euo pipefail` makes any unguarded failure inside the helpers visible.
    prog = f'set -euo pipefail; source "{SCRIPT}"; {snippet}'
    return subprocess.run(
        [BASH, "-c", prog], cwd=cwd, capture_output=True, text=True, timeout=30, check=False
    )


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@pytest.mark.parametrize("mode", [0o600, 0o640])
def test_env_survives_a_wipe_and_restore_round_trip(tmp_path, mode):
    dist = tmp_path / "dist"
    (dist / "world-intel").mkdir(parents=True)
    env = dist / "world-intel" / ".env"
    env.write_text("OPENAI_API_KEY=sk-test\nFRED_API_KEY=abc=def\n", encoding="utf-8")
    os.chmod(env, mode)
    backup = tmp_path / "bak" / ".env"
    backup.parent.mkdir()

    r = _call(
        f'backup_dist_env "{dist}" "{backup}"; rm -rf "{dist}"; '
        f'mkdir -p "{dist}/world-intel"; restore_dist_env "{dist}" "{backup}"',
        tmp_path,
    )
    assert r.returncode == 0, r.stderr
    assert env.read_text(encoding="utf-8") == "OPENAI_API_KEY=sk-test\nFRED_API_KEY=abc=def\n"
    assert _mode(env) == mode


def test_missing_env_is_not_an_error_and_creates_nothing(tmp_path):
    dist = tmp_path / "dist"
    (dist / "world-intel").mkdir(parents=True)
    backup = tmp_path / "bak" / ".env"
    backup.parent.mkdir()

    r = _call(f'backup_dist_env "{dist}" "{backup}"; restore_dist_env "{dist}" "{backup}"', tmp_path)
    assert r.returncode == 0, r.stderr
    assert not backup.exists()
    assert not (dist / "world-intel" / ".env").exists()


def test_missing_dist_dir_is_not_an_error(tmp_path):
    backup = tmp_path / "bak" / ".env"
    backup.parent.mkdir()
    r = _call(
        f'backup_dist_env "{tmp_path}/nope" "{backup}"; restore_dist_env "{tmp_path}/nope" "{backup}"',
        tmp_path,
    )
    assert r.returncode == 0, r.stderr


def test_sourcing_the_script_does_not_start_a_build(tmp_path):
    """The main flow must be guarded so `source` only defines functions."""
    r = _call("type backup_dist_env restore_dist_env >/dev/null", tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Built:" not in r.stdout
    assert not (tmp_path / "dist").exists()


def test_build_flow_backs_up_before_wiping_and_restores_after_building():
    src = SCRIPT.read_text(encoding="utf-8")
    assert 'BASH_SOURCE[0]}" == "$0"' in src
    i_backup = src.index("backup_dist_env", src.index("main()"))
    i_wipe = src.index('rm -rf "$ROOT/build" "$ROOT/dist"')
    i_build = src.index('"$VENV/bin/pyinstaller"')
    i_restore = src.index("restore_dist_env", i_build)
    assert i_backup < i_wipe < i_build < i_restore
