#!/usr/bin/env python3
"""Black-box checks for dist/world-intel/world-intel.

Runs from a temp directory with a scrubbed environment and temp HOME, and
verifies *content* (Chinese text, exact MCP tool-name set, served HTML),
not just exit codes.  HOME, cwd and the children's stderr files live in one
temp tree that is removed only after every child process has been waited on.

    .venv/bin/python -c "import json;from world_intel_mcp.tools import ALL_TOOLS;print(json.dumps(sorted(x.name for x in ALL_TOOLS)))" > /tmp/expected-tools.json
    python3 -I scripts/verify-macos-build.py --exe dist/world-intel/world-intel \
        --expected-tools /tmp/expected-tools.json
"""

from __future__ import annotations

import argparse
import json
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

# Timeouts (seconds) are module constants so tests can shorten them.
HELP_TIMEOUT = 60
MCP_RECV_TIMEOUT = 90.0
DASHBOARD_READY_TIMEOUT = 60.0
PROC_WAIT_TIMEOUT = 10
POLL_INTERVAL = 0.5
STDERR_TAIL_LINES = 40

FAILURES: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        FAILURES.append(msg)


class Sandbox:
    """HOME, cwd and child stderr files under one base directory.

    The caller owns the enclosing ``TemporaryDirectory``, so everything goes
    away together and only after the children have exited.
    """

    def __init__(self, base: str | Path) -> None:
        self.base = Path(base)
        self.home = self.base / "home"
        self.cwd = self.base / "cwd"
        self.home.mkdir(exist_ok=True)
        self.cwd.mkdir(exist_ok=True)

    def env(self, extra: dict | None = None) -> dict:
        env = {"PATH": "/usr/bin:/bin", "HOME": str(self.home)}
        env.update(extra or {})
        return env

    def stderr_path(self, name: str) -> Path:
        return self.base / f"{name}.stderr"


def stderr_tail(path: Path, lines: int = STDERR_TAIL_LINES) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(no stderr file)"
    return "\n".join(text.splitlines()[-lines:]) or "(stderr empty)"


def print_stderr_tail(label: str, path: Path) -> None:
    print(f"---- {label} stderr tail ----\n{stderr_tail(path)}\n----", flush=True)


def run(exe: str, args: list[str], sb: Sandbox, timeout: float | None = None):
    timeout = HELP_TIMEOUT if timeout is None else timeout
    try:
        return subprocess.run([exe, *args], capture_output=True, text=True, cwd=sb.cwd, env=sb.env(),
                              timeout=timeout)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess([exe, *args], -1, "", f"timed out after {timeout}s")


def check_help(exe: str, sb: Sandbox) -> None:
    zh = run(exe, ["--help"], sb)
    check("用法" in zh.stdout, "top-level --help is zh-TW by default")
    cli_zh = run(exe, ["cli", "--help"], sb)
    check("選項" in cli_zh.stdout and "Usage:" not in cli_zh.stdout, "cli --help is zh-TW (Click chrome translated)")
    cli_en = run(exe, ["--lang", "en", "cli", "--help"], sb)
    check("Usage:" in cli_en.stdout and "選項" not in cli_en.stdout, "--lang en before subcommand switches to English")


def check_mcp(exe: str, sb: Sandbox, expected: set[str], recv_timeout: float | None = None) -> None:
    recv_timeout = MCP_RECV_TIMEOUT if recv_timeout is None else recv_timeout
    failures_before = len(FAILURES)
    err_path = sb.stderr_path("mcp")
    err_file = open(err_path, "wb")
    proc = subprocess.Popen(
        [exe, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err_file,
        text=True, cwd=sb.cwd, env=sb.env(),
    )
    lines: "queue.Queue[str | None]" = queue.Queue()

    def pump() -> None:  # reader thread: gives recv() a real timeout
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()

    def send(obj: dict) -> None:
        try:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
        except OSError:  # child already exited; recv() reports the failure
            pass

    def recv(msg_id: int, timeout: float = recv_timeout) -> dict | None:
        """Next JSON-RPC response with this id; notifications are skipped."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = lines.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if line is None:  # EOF: child exited; keep the sentinel so later recv() calls return at once
                lines.put(None)
                break
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                check(False, f"MCP stdout carried non-JSON-RPC output: {line[:80]!r}")
                continue
            if msg.get("id") == msg_id:
                return msg
        return None

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                         "clientInfo": {"name": "verify", "version": "0"}}})
        init = recv(1)
        check(bool(init and init.get("result", {}).get("serverInfo")), "MCP initialize returns serverInfo")
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = recv(2)
        tools = (resp or {}).get("result", {}).get("tools")
        check(tools is not None, "MCP tools/list answered before timeout")
        if tools is None:
            return
        names = {t["name"] for t in tools}
        check(names == expected, f"MCP tool-name set equals source registry ({len(names)} vs {len(expected)}); "
                                 f"missing={sorted(expected - names)[:5]} extra={sorted(names - expected)[:5]}")
        check(all(t.get("inputSchema") for t in tools), "every MCP tool carries an inputSchema")
    finally:
        proc.kill()
        proc.wait(timeout=PROC_WAIT_TIMEOUT)
        err_file.close()
        if len(FAILURES) > failures_before:
            print_stderr_tail("mcp", err_path)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_dashboard(exe: str, sb: Sandbox, ready_timeout: float | None = None) -> None:
    ready_timeout = DASHBOARD_READY_TIMEOUT if ready_timeout is None else ready_timeout
    failures_before = len(FAILURES)
    err_path = sb.stderr_path("dashboard")
    err_file = open(err_path, "wb")
    port = free_port()
    proc = subprocess.Popen([exe, "dashboard", "--port", str(port)], stdout=subprocess.DEVNULL,
                            stderr=err_file, cwd=sb.cwd, env=sb.env())
    try:
        body = None
        exited = None
        deadline = time.time() + ready_timeout
        # Poll: the child process exposes readiness only through its listening port.
        while time.time() < deadline and body is None:
            exited = proc.poll()
            if exited is not None:  # died before serving: no point waiting out the deadline
                break
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read().decode("utf-8")
            except OSError:
                time.sleep(POLL_INTERVAL)
        if exited is not None and body is None:
            check(False, f"dashboard process exited early (rc={exited}) before serving GET /")
            return
        check(body is not None, "dashboard serves GET / from a non-project directory")
        if body is None:
            return
        check('<html lang="zh-Hant-TW">' in body, "dashboard html lang is zh-Hant-TW")
        check("window.__I18N__ = {" in body and "圖層" in body, "dashboard injects the zh-TW catalog")
        api = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/aois", timeout=10).read().decode("utf-8")
        json.loads(api)
        check(True, "dashboard /api/aois returns valid JSON")
    finally:
        proc.kill()
        proc.wait(timeout=PROC_WAIT_TIMEOUT)
        err_file.close()
        if len(FAILURES) > failures_before:
            print_stderr_tail("dashboard", err_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument(
        "--expected-tools", required=True,
        help="JSON file holding the sorted tool-name list of the source registry. Generate it with: "
             ".venv/bin/python -c \"import json;from world_intel_mcp.tools import ALL_TOOLS;"
             "print(json.dumps(sorted(x.name for x in ALL_TOOLS)))\" > /tmp/expected-tools.json",
    )
    a = ap.parse_args(argv)
    exe = str(Path(a.exe).resolve())
    expected = set(json.loads(Path(a.expected_tools).read_text()))
    # One temp tree for HOME + cwd + stderr files; removed only after every child has been waited on.
    with tempfile.TemporaryDirectory(prefix="wi-verify-") as base:
        sb = Sandbox(base)
        check_help(exe, sb)
        check_mcp(exe, sb, expected)
        check_dashboard(exe, sb)
    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
