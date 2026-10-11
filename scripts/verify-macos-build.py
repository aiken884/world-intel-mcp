#!/usr/bin/env python3
"""Black-box checks for dist/world-intel/world-intel.

Runs from a temp directory with a scrubbed environment and temp HOME, and
verifies *content* (Chinese text, exact MCP tool-name set, served HTML),
not just exit codes.

    python3 -I scripts/verify-macos-build.py --exe dist/world-intel/world-intel \
        --expected-tools /path/expected-tools.json
"""

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

FAILURES: list[str] = []


def check(ok: bool, msg: str) -> None:
    print(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        FAILURES.append(msg)


def scrubbed_env(extra: dict | None = None) -> dict:
    env = {"PATH": "/usr/bin:/bin", "HOME": tempfile.mkdtemp(prefix="wi-home-")}
    env.update(extra or {})
    return env


def run(exe: str, args: list[str], cwd: str, env: dict, timeout: int = 60):
    return subprocess.run([exe, *args], capture_output=True, text=True, cwd=cwd, env=env, timeout=timeout)


def check_help(exe: str, cwd: str) -> None:
    zh = run(exe, ["--help"], cwd, scrubbed_env())
    check("用法" in zh.stdout, "top-level --help is zh-TW by default")
    cli_zh = run(exe, ["cli", "--help"], cwd, scrubbed_env())
    check("選項" in cli_zh.stdout and "Usage:" not in cli_zh.stdout, "cli --help is zh-TW (Click chrome translated)")
    cli_en = run(exe, ["--lang", "en", "cli", "--help"], cwd, scrubbed_env())
    check("Usage:" in cli_en.stdout and "選項" not in cli_en.stdout, "--lang en before subcommand switches to English")


def check_mcp(exe: str, cwd: str, expected: set[str]) -> None:
    proc = subprocess.Popen(
        [exe, "mcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, cwd=cwd, env=scrubbed_env(),
    )
    lines: "queue.Queue[str | None]" = queue.Queue()

    def pump() -> None:  # reader thread: gives recv() a real timeout
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=pump, daemon=True).start()

    def send(obj: dict) -> None:
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def recv(msg_id: int, timeout: float = 90.0) -> dict | None:
        """Next JSON-RPC response with this id; notifications are skipped."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = lines.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if line is None:
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
        proc.wait(timeout=10)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_dashboard(exe: str, cwd: str) -> None:
    port = free_port()
    proc = subprocess.Popen([exe, "dashboard", "--port", str(port)], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, cwd=cwd, env=scrubbed_env())
    try:
        body = None
        deadline = time.time() + 60
        # Poll: the child process exposes readiness only through its listening port.
        while time.time() < deadline and body is None:
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=3).read().decode("utf-8")
            except OSError:
                time.sleep(0.5)
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
        proc.wait(timeout=10)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", required=True)
    ap.add_argument("--expected-tools", required=True)
    a = ap.parse_args()
    exe = str(Path(a.exe).resolve())
    expected = set(json.loads(Path(a.expected_tools).read_text()))
    cwd = tempfile.mkdtemp(prefix="wi-cwd-")
    check_help(exe, cwd)
    check_mcp(exe, cwd, expected)
    check_dashboard(exe, cwd)
    print(f"\n{len(FAILURES)} failure(s)")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
