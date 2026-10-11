"""Hygiene tests for scripts/verify-macos-build.py and scripts/verify-macos-app.py.

The scripts are loaded by path (their file names contain hyphens) and driven
against tiny fake executables written into tmp_path.  Nothing here launches a
PyInstaller artefact.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


def _load(filename: str, modname: str):
    spec = importlib.util.spec_from_file_location(modname, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def vb():
    return _load("verify-macos-build.py", "verify_macos_build")


@pytest.fixture
def va():
    return _load("verify-macos-app.py", "verify_macos_app")


def _fake(path: Path, body: str) -> Path:
    path.write_text(f"#!{sys.executable}\n{body}")
    path.chmod(0o755)
    return path


def _shorten(vb, monkeypatch, *, help_t=1, recv_t=1.0, ready_t=1.0) -> None:
    monkeypatch.setattr(vb, "HELP_TIMEOUT", help_t)
    monkeypatch.setattr(vb, "MCP_RECV_TIMEOUT", recv_t)
    monkeypatch.setattr(vb, "DASHBOARD_READY_TIMEOUT", ready_t)


def _expected(tmp_path: Path, names=("a",)) -> Path:
    p = tmp_path / "expected.json"
    p.write_text(json.dumps(list(names)))
    return p


# A fake world-intel executable that answers every sub-command correctly and
# records the HOME / cwd it was given (and whether they existed at the time).
HAPPY_BODY = r'''
import json, os, sys
rec = {rec!r}
with open(rec, "a") as f:
    f.write(json.dumps({{"home": os.environ["HOME"], "cwd": os.getcwd(),
                        "home_exists": os.path.isdir(os.environ["HOME"])}}) + "\n")
args = sys.argv[1:]
if args[:1] == ["--help"]:
    print("用法")
elif args == ["cli", "--help"]:
    print("選項")
elif args[:1] == ["--lang"]:
    print("Usage:")
elif args[:1] == ["mcp"]:
    for line in sys.stdin:
        msg = json.loads(line)
        if msg.get("method") == "initialize":
            print(json.dumps({{"jsonrpc": "2.0", "id": msg["id"],
                               "result": {{"serverInfo": {{"name": "fake"}}}}}}), flush=True)
        elif msg.get("method") == "tools/list":
            print(json.dumps({{"jsonrpc": "2.0", "id": msg["id"], "result": {{"tools": [
                {{"name": "a", "inputSchema": {{"type": "object"}}}}]}}}}), flush=True)
elif args[:1] == ["dashboard"]:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    port = int(args[args.index("--port") + 1])
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/api/aois":
                body = b"[]"
            else:
                body = ('<html lang="zh-Hant-TW"><script>window.__I18N__ = {{"x": "圖層"}}'
                        '</script></html>').encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass
    HTTPServer(("127.0.0.1", port), H).serve_forever()
'''


def test_scripts_have_future_annotations():
    """`dict | None` signatures raise TypeError at def time on 3.9 without it."""
    for name in ("verify-macos-build.py", "verify-macos-app.py"):
        tree = ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))
        assert any(
            isinstance(n, ast.ImportFrom) and n.module == "__future__"
            and any(a.name == "annotations" for a in n.names)
            for n in tree.body
        ), name


def test_build_happy_path_passes_and_cleans_tempdir(vb, tmp_path, capsys):
    rec = tmp_path / "rec.jsonl"
    exe = _fake(tmp_path / "fake-exe", HAPPY_BODY.format(rec=str(rec)))
    rc = vb.main(["--exe", str(exe), "--expected-tools", str(_expected(tmp_path))])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "FAIL" not in out
    records = [json.loads(line) for line in rec.read_text().splitlines()]
    assert records and all(r["home_exists"] for r in records)
    homes = {os.path.realpath(r["home"]) for r in records}
    cwds = {os.path.realpath(r["cwd"]) for r in records}
    assert len(homes) == 1 and len(cwds) == 1  # one HOME, one cwd, shared
    assert Path(next(iter(homes))).parent == Path(next(iter(cwds))).parent  # same temp root
    assert not Path(next(iter(homes))).parent.exists()  # removed after the run


def test_build_tempdir_removed_even_when_a_check_raises(vb, tmp_path, monkeypatch):
    rec = tmp_path / "rec.jsonl"
    exe = _fake(tmp_path / "fake-exe", HAPPY_BODY.format(rec=str(rec)))

    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(vb, "check_dashboard", boom)
    with pytest.raises(RuntimeError):
        vb.main(["--exe", str(exe), "--expected-tools", str(_expected(tmp_path))])
    home = Path(json.loads(rec.read_text().splitlines()[0])["home"])
    assert not home.parent.exists()


def test_build_early_exit_fails_fast_with_stderr_tail(vb, tmp_path, monkeypatch, capsys):
    body = (
        "import sys\n"
        "for i in range(1, 101):\n"
        "    sys.stderr.write(f'err-line-{i}\\n')\n"
        "sys.exit(3)\n"
    )
    exe = _fake(tmp_path / "fake-exe", body)
    monkeypatch.setattr(vb, "HELP_TIMEOUT", 10)
    monkeypatch.setattr(vb, "MCP_RECV_TIMEOUT", 30.0)  # must NOT be waited out either
    monkeypatch.setattr(vb, "DASHBOARD_READY_TIMEOUT", 30.0)  # must NOT be waited out
    started = time.monotonic()
    rc = vb.main(["--exe", str(exe), "--expected-tools", str(_expected(tmp_path))])
    elapsed = time.monotonic() - started
    out = capsys.readouterr().out
    assert rc == 1
    assert elapsed < 15, f"early exit was waited out to a deadline ({elapsed:.1f}s)"
    assert any("exited early" in f for f in vb.FAILURES), vb.FAILURES
    lines = out.splitlines()
    assert "err-line-100" in lines  # tail is the end of the file...
    assert "err-line-61" in lines
    assert "err-line-60" not in lines  # ...limited to the last 40 lines
    assert "err-line-1" not in lines


def test_build_hanging_exe_times_out_with_fail_not_hang(vb, tmp_path, monkeypatch, capsys):
    exe = _fake(tmp_path / "fake-exe", "import time\ntime.sleep(60)\n")
    _shorten(vb, monkeypatch)
    started = time.monotonic()
    rc = vb.main(["--exe", str(exe), "--expected-tools", str(_expected(tmp_path))])
    elapsed = time.monotonic() - started
    capsys.readouterr()
    assert rc == 1
    assert elapsed < 30
    msgs = "\n".join(vb.FAILURES)
    assert "tools/list answered before timeout" in msgs
    assert "dashboard serves GET /" in msgs
    assert "top-level --help" in msgs  # a timed-out help run is a FAIL, not a traceback


def test_build_expected_tools_help_documents_how_to_generate(vb, capsys):
    with pytest.raises(SystemExit):
        vb.main(["--help"])
    flat = " ".join(capsys.readouterr().out.split())
    assert "ALL_TOOLS" in flat and "expected-tools.json" in flat


# ---- verify-macos-app.py ---------------------------------------------------


def _fake_app(tmp_path: Path, body: str) -> str:
    exe_dir = tmp_path / "Fake.app" / "Contents" / "MacOS"
    exe_dir.mkdir(parents=True)
    _fake(exe_dir / "World Intel", body)
    return str(tmp_path / "Fake.app")


SMOKE_BODY = r'''
import json, os, sys
{noise}
data = {{"mode": "window", "lang": "zh-Hant-TW", "hasI18N": 500, "layers": True,
         "openUrlApi": True, "url": "http://127.0.0.1:1/"}}
with open(os.environ["WORLD_INTEL_GUI_SMOKE_OUT"], "w") as f:
    json.dump(data, f)
'''


def _cleanup(va) -> None:
    import shutil

    for d in va.TEMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)


def test_app_smoke_passes_with_voluminous_output(va, tmp_path, monkeypatch, capsys):
    """Output far beyond a pipe buffer (64 KiB) must not stall the launched app."""
    noise = "sys.stdout.write('x' * 1_000_000); sys.stderr.write('y' * 1_000_000)"
    app = _fake_app(tmp_path, SMOKE_BODY.format(noise=noise))
    monkeypatch.setattr(va, "SMOKE_TIMEOUT", 15)
    try:
        data = va.run_smoke(app, "fake app")
    finally:
        _cleanup(va)
    out = capsys.readouterr().out
    assert data is not None and data["lang"] == "zh-Hant-TW", out
    assert not [f for f in va.FAILURES if "finished within" in f], va.FAILURES


def test_app_smoke_hang_reports_failure_and_returns_none(va, tmp_path, monkeypatch, capsys):
    app = _fake_app(tmp_path, "import time\ntime.sleep(60)\n")
    monkeypatch.setattr(va, "SMOKE_TIMEOUT", 1)
    try:
        data = va.run_smoke(app, "hang")
    finally:
        _cleanup(va)
    capsys.readouterr()
    assert data is None
    assert any("finished within 1s" in f for f in va.FAILURES)


def test_app_smoke_failure_prints_app_output_tail(va, tmp_path, monkeypatch, capsys):
    app = _fake_app(tmp_path, "import sys\nsys.stderr.write('app-crashed-here\\n')\nsys.exit(2)\n")
    monkeypatch.setattr(va, "SMOKE_TIMEOUT", 10)
    try:
        data = va.run_smoke(app, "crash")
    finally:
        _cleanup(va)
    out = capsys.readouterr().out
    assert data is None
    assert "app-crashed-here" in out
    assert any("wrote the smoke result file" in f for f in va.FAILURES)
