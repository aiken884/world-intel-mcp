#!/usr/bin/env python3
"""Black-box acceptance checks for "World Intel.app" and its DMG.

Standard library only; run with ``python3 -I``:

    python3 -I scripts/verify-macos-app.py \
        --app "dist/World Intel.app" --dmg dist/World-Intel-0.10.0-arm64.dmg

Every launch uses a scrubbed environment and a throw-away HOME.  The app is
started in smoke mode (``WORLD_INTEL_GUI_SMOKE_OUT``): once the real WKWebView
has loaded the dashboard it writes what the page actually shows (language,
translation catalog size, the translated 圖層 label) to a file and exits.  The
checks assert that *content*, not just an exit code.

Exit code 0 only if every check passes.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from contextlib import closing
from pathlib import Path

FAILURES: list[str] = []
CHILDREN: list[subprocess.Popen] = []
TEMP_DIRS: list[str] = []
SMOKE_TIMEOUT = 90


def check(ok: bool, msg: str) -> bool:
    print(("PASS  " if ok else "FAIL  ") + msg, flush=True)
    if not ok:
        FAILURES.append(msg)
    return ok


def tmpdir(prefix: str) -> str:
    # realpath: macOS TMPDIR is under /var -> /private/var; keep paths canonical.
    d = os.path.realpath(tempfile.mkdtemp(prefix=prefix))
    TEMP_DIRS.append(d)
    return d


def exe_of(app: str) -> str:
    return str(Path(app) / "Contents" / "MacOS" / "World Intel")


def clean_env(home: str, extra: dict | None = None) -> dict:
    env = {"PATH": "/usr/bin:/bin", "HOME": home, "TMPDIR": tmpdir("wi-tmp-") + "/"}
    env.update(extra or {})
    return env


def log_tail(home: str, lines: int = 40) -> str:
    log = Path(home) / "Library" / "Logs" / "World Intel" / "world-intel.log"
    try:
        return "\n".join(log.read_text(errors="replace").splitlines()[-lines:])
    except OSError:
        return "(no log file)"


def port_free(port: int) -> bool:
    """Nothing is listening on the loopback port any more.

    Connect rather than bind: connections the window made leave TIME_WAIT
    entries that make a plain bind() fail although nobody is listening.
    """
    with closing(socket.socket()) as s:
        s.settimeout(2)
        return s.connect_ex(("127.0.0.1", port)) != 0


def occupy(port: int) -> socket.socket | None:
    """Listen on a loopback port (None if somebody else already has it)."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("127.0.0.1", port))
        s.listen(1)
    except OSError:
        s.close()
        return None
    return s


def kill(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)


def run_smoke(app: str, label: str, extra_env: dict | None = None, expect_mode: str = "window") -> dict | None:
    """Launch the app in smoke mode and assert on what the page showed."""
    home = tmpdir("wi-home-")
    out = os.path.join(tmpdir("wi-out-"), "smoke.json")
    env = clean_env(home, {"WORLD_INTEL_GUI_SMOKE_OUT": out, **(extra_env or {})})
    proc = subprocess.Popen(
        [exe_of(app)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=home
    )
    CHILDREN.append(proc)
    try:
        rc = proc.wait(SMOKE_TIMEOUT)
    except subprocess.TimeoutExpired:
        kill(proc)
        check(False, f"{label}: finished within {SMOKE_TIMEOUT}s")
        print("---- app log tail ----\n" + log_tail(home) + "\n----", flush=True)
        return None
    output = proc.stdout.read() if proc.stdout else ""
    if not check(os.path.exists(out), f"{label}: wrote the smoke result file"):
        print("---- app output ----\n" + output[-2000:] + "\n---- app log tail ----\n" + log_tail(home), flush=True)
        check(rc == 0, f"{label}: process exit code 0 (got {rc})")
        return None
    data = json.loads(Path(out).read_text(encoding="utf-8"))
    check("error" not in data, f"{label}: no error in smoke result ({data.get('error')})")
    check(data.get("mode") == expect_mode, f"{label}: mode == {expect_mode} (got {data.get('mode')})")
    check(data.get("lang") == "zh-Hant-TW", f"{label}: <html lang> is zh-Hant-TW (got {data.get('lang')!r})")
    n = data.get("hasI18N", 0)
    check(isinstance(n, int) and n > 100, f"{label}: zh-TW catalog injected ({n} entries)")
    check(data.get("layers") is True, f"{label}: translated label 圖層 is rendered")
    if expect_mode == "window":
        check(
            data.get("openUrlApi") is True,
            f"{label}: window.pywebview.api.open_url bridge is available to the page",
        )
    url = str(data.get("url", ""))
    check(url.startswith("http://127.0.0.1:"), f"{label}: served from loopback ({url})")
    check(rc == 0, f"{label}: process exit code 0 (got {rc})")
    try:
        port = int(url.split(":")[2].split("/")[0])
        check(port_free(port), f"{label}: port {port} released after exit")
    except (IndexError, ValueError):
        check(False, f"{label}: could not parse port from url {url!r}")
    if rc != 0:
        print("---- app log tail ----\n" + log_tail(home), flush=True)
    return data


def wait_for(predicate, timeout: float, interval: float = 0.25):
    """Bounded wait on an *external* process we cannot subscribe to."""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(interval)
    return None


def http_200(url: str) -> bool:
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


def read_instance(home: str) -> dict | None:
    p = Path(home) / "Library" / "Application Support" / "World Intel" / "instance.json"
    try:
        return json.loads(p.read_text())
    except (OSError, ValueError):
        return None


def check_codesign(app: str, label: str) -> None:
    r = subprocess.run(
        ["codesign", "--verify", "--deep", "--strict", app], capture_output=True, text=True
    )
    check(r.returncode == 0, f"{label}: codesign --verify --deep --strict {r.stderr.strip()[:200]}")


def check_single_instance(app: str) -> None:
    """Real (non-smoke) windows: second launch defers; stale lock is taken over."""
    home = tmpdir("wi-home-")
    rec_dir = tmpdir("wi-browser-")
    record = os.path.join(rec_dir, "opened.txt")
    script = os.path.join(rec_dir, "fake-browser.sh")
    Path(script).write_text(f'#!/bin/sh\necho "$1" >> "{record}"\n')
    os.chmod(script, os.stat(script).st_mode | stat.S_IXUSR)
    env = clean_env(home, {"BROWSER": f"{script} %s"})

    first = subprocess.Popen([exe_of(app)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=home)
    CHILDREN.append(first)
    info = wait_for(lambda: read_instance(home), 60)
    url = f"http://127.0.0.1:{info['port']}/" if info else ""
    check(bool(info) and info.get("pid") == first.pid, "single-instance: first instance published its pid/port")
    check(bool(url) and wait_for(lambda: http_200(url), 30) is True, "single-instance: first instance answers 200 on /")

    second = subprocess.Popen([exe_of(app)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=home)
    CHILDREN.append(second)
    try:
        rc2 = second.wait(60)
    except subprocess.TimeoutExpired:
        kill(second)
        rc2 = None
    check(rc2 == 0, f"single-instance: second launch exits 0 by itself (got {rc2})")
    opened = Path(record).read_text().split() if os.path.exists(record) else []
    check(opened == [url], f"single-instance: second launch opened the running instance's URL ({opened})")
    check(first.poll() is None, "single-instance: first instance still running")
    info2 = read_instance(home)
    check(bool(info2) and info2.get("port") == (info or {}).get("port"), "single-instance: no second server was started")

    # Stale takeover: SIGKILL leaves instance.json behind; the kernel drops the lock.
    first.send_signal(signal.SIGKILL)
    first.wait(10)
    port = (info or {}).get("port")
    check(port is not None and wait_for(lambda: port_free(port), 10) is True, "stale: port released after SIGKILL")
    third = subprocess.Popen([exe_of(app)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=home)
    CHILDREN.append(third)
    info3 = wait_for(lambda: (lambda i: i if i and i.get("pid") == third.pid else None)(read_instance(home)), 60)
    check(bool(info3), "stale: new launch took over the dead instance's lock and published itself")
    url3 = f"http://127.0.0.1:{info3['port']}/" if info3 else ""
    check(bool(url3) and wait_for(lambda: http_200(url3), 30) is True, "stale: takeover instance answers 200 on /")
    if not info3:
        print("---- app log tail ----\n" + log_tail(home), flush=True)
    kill(third)


def check_port_conflicts(app: str) -> None:
    """8501 (CLI dashboard) and 18501 (app's preferred port) are both taken."""
    held = {p: occupy(p) for p in (8501, 18501)}
    try:
        # A port we could not grab is already held by someone else: still a conflict.
        data = run_smoke(app, "port-conflict (8501 and 18501 occupied)")
        if data:
            port = int(str(data["url"]).split(":")[2].split("/")[0])
            check(port not in (8501, 18501), f"port-conflict: app used a different free port ({port})")
    finally:
        for s in held.values():
            if s:
                s.close()


def check_dmg(dmg: str) -> None:
    mount = tmpdir("wi-mnt-")
    attach = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", mount, dmg],
        capture_output=True, text=True,
    )
    if not check(attach.returncode == 0, f"dmg: attach ({attach.stderr.strip()[:200]})"):
        return
    try:
        app_in = os.path.join(mount, "World Intel.app")
        link = os.path.join(mount, "Applications")
        check(os.path.isdir(app_in), "dmg: contains World Intel.app")
        check(os.path.islink(link) and os.readlink(link) == "/Applications", "dmg: Applications is a symlink to /Applications")
        if os.path.isdir(app_in):
            dest = os.path.join(tmpdir("wi-inst-"), "World Intel.app")
            cp = subprocess.run(["ditto", app_in, dest], capture_output=True, text=True)
            check(cp.returncode == 0, "dmg: app copied out of the image (drag-install)")
            if cp.returncode == 0:
                check_codesign(dest, "dmg copy")
                run_smoke(dest, "dmg copy")
    finally:
        det = subprocess.run(["hdiutil", "detach", mount], capture_output=True, text=True)
        if det.returncode != 0:
            subprocess.run(["hdiutil", "detach", "-force", mount], capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app", required=True, help='path to "World Intel.app"')
    ap.add_argument("--dmg", help="path to World-Intel-<ver>-arm64.dmg")
    ap.add_argument("--skip-single-instance", action="store_true", help="skip the real-window single-instance test")
    args = ap.parse_args()

    app = os.path.abspath(args.app)
    try:
        if not check(os.path.isfile(exe_of(app)), f"app executable exists: {exe_of(app)}"):
            return 1
        check_codesign(app, "app")
        run_smoke(app, "app")
        run_smoke(app, "app (browser fallback)", {"WORLD_INTEL_GUI_FORCE_BROWSER": "1"}, expect_mode="browser")
        check_port_conflicts(app)
        if not args.skip_single_instance:
            check_single_instance(app)
        if args.dmg:
            check_dmg(os.path.abspath(args.dmg))
    finally:
        for p in CHILDREN:
            kill(p)
        for d in TEMP_DIRS:
            shutil.rmtree(d, ignore_errors=True)

    print()
    if FAILURES:
        print(f"{len(FAILURES)} failure(s):")
        for f in FAILURES:
            print("  - " + f)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
