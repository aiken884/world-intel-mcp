"""Tests for the macOS GUI app entry (``world_intel_mcp.gui_app``).

The pieces that need a real window (pywebview) are exercised through a fake
``webview`` module; everything else (free port, ``.env`` loading, single
instance, URL validation, the uvicorn thread, smoke output) runs for real.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import types
import urllib.request
from pathlib import Path

import pytest
from starlette.applications import Starlette
from starlette.responses import HTMLResponse
from starlette.routing import Route

from world_intel_mcp import gui_app


# ── helpers ─────────────────────────────────────────────────────────────────

PAGE = (
    '<html lang="zh-Hant-TW"><head><title>Phoenix Intelligence Dashboard</title>'
    "<script>window.__I18N__ = " + json.dumps({f"k{i}": f"v{i}" for i in range(150)}) + ";</script>"
    "</head><body><span>圖層</span></body></html>"
)


def _tiny_app() -> Starlette:
    async def index(request):
        return HTMLResponse(PAGE)

    return Starlette(routes=[Route("/", index)])


def _port_free(port: int) -> bool:
    """True when a server could bind the port right now.

    SO_REUSEADDR mirrors what a restarting server does: connections left in
    TIME_WAIT by the requests just served must not count as "still in use",
    only a live listener does.
    """
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 (loopback)
        return r.status, r.read().decode()


# ── free port ───────────────────────────────────────────────────────────────


def test_bind_socket_returns_listening_loopback_socket():
    s = gui_app.bind_socket(preferred=None)
    try:
        host, port = s.getsockname()
        assert host == "127.0.0.1" and port > 0
        # Already listening: a client can connect without a second bind.
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass
    finally:
        s.close()


def test_bind_socket_two_calls_never_collide():
    a = gui_app.bind_socket(preferred=None)
    b = gui_app.bind_socket(preferred=None)
    try:
        assert a.getsockname()[1] != b.getsockname()[1]
    finally:
        a.close()
        b.close()


def test_bind_socket_uses_preferred_port_when_free_else_falls_back():
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()

    first = gui_app.bind_socket(preferred=port)
    try:
        assert first.getsockname()[1] == port
        second = gui_app.bind_socket(preferred=port)  # taken -> falls back
        try:
            assert second.getsockname()[1] not in (0, port)
        finally:
            second.close()
    finally:
        first.close()


def test_bind_socket_never_takes_8501_requirement():
    """Occupying 8501 (the CLI dashboard default) must not matter."""
    blocker = socket.socket()
    try:
        blocker.bind(("127.0.0.1", 8501))
    except OSError:
        pytest.skip("8501 already in use on this machine")
    try:
        s = gui_app.bind_socket()
        try:
            assert s.getsockname()[1] != 8501
        finally:
            s.close()
    finally:
        blocker.close()


# ── .env loading ────────────────────────────────────────────────────────────


def test_load_user_env_sets_missing_keys_and_keeps_existing(tmp_path, monkeypatch):
    sdir = tmp_path / "World Intel"
    sdir.mkdir()
    (sdir / ".env").write_text("WI_TEST_NEW=from-file\nWI_TEST_OLD=from-file\n")
    monkeypatch.delenv("WI_TEST_NEW", raising=False)
    monkeypatch.setenv("WI_TEST_OLD", "from-shell")
    assert gui_app.load_user_env(sdir) is True
    assert os.environ["WI_TEST_NEW"] == "from-file"
    assert os.environ["WI_TEST_OLD"] == "from-shell"
    monkeypatch.delenv("WI_TEST_NEW", raising=False)


def test_load_user_env_missing_dir_is_skipped_and_not_created(tmp_path):
    sdir = tmp_path / "does-not-exist"
    assert gui_app.load_user_env(sdir) is False
    assert not sdir.exists()


def test_load_user_env_dir_without_env_file(tmp_path):
    assert gui_app.load_user_env(tmp_path) is False


def test_support_and_log_dirs_live_under_home(tmp_path):
    assert gui_app.support_dir(tmp_path) == tmp_path / "Library/Application Support/World Intel"
    assert gui_app.log_dir(tmp_path) == tmp_path / "Library/Logs/World Intel"


# ── external URLs ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url,ok",
    [
        ("http://example.com/a?b=1", True),
        ("https://example.com", True),
        ("HTTPS://EXAMPLE.COM", True),
        ("javascript:alert(1)", False),
        ("file:///etc/passwd", False),
        ("ftp://example.com/x", False),
        ("data:text/html,hi", False),
        ("//example.com", False),
        ("https://", False),
        ("", False),
        (None, False),
        (123, False),
    ],
)
def test_is_safe_external_url(url, ok):
    assert gui_app.is_safe_external_url(url) is ok


def test_api_open_url_only_passes_http_and_https():
    opened: list[str] = []
    api = gui_app.Api(opener=opened.append)
    assert api.open_url("https://example.com/x") is True
    assert api.open_url("javascript:alert(1)") is False
    assert api.open_url("file:///etc/hosts") is False
    assert opened == ["https://example.com/x"]


def test_api_exposes_only_open_url():
    public = [n for n in dir(gui_app.Api(opener=lambda u: None)) if not n.startswith("_")]
    assert public == ["open_url"]


# ── single instance ─────────────────────────────────────────────────────────


def test_first_claim_owns_and_second_sees_existing(tmp_path):
    first = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    try:
        assert first.kind == "owner"
        first.publish(54321)
        info = json.loads((tmp_path / "instance.json").read_text())
        assert info == {"pid": os.getpid(), "port": 54321}

        second = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
        assert second.kind == "existing"
        assert second.url == "http://127.0.0.1:54321/"
    finally:
        first.close()


def test_claim_after_owner_exit_takes_over_stale_lock_and_file(tmp_path):
    first = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    first.publish(54321)
    first.close()  # lock released, instance.json removed or stale
    again = gui_app.claim_instance(tmp_path, probe=lambda url: False, wait=0)
    try:
        assert again.kind == "owner"
    finally:
        again.close()


def test_stale_instance_json_with_dead_pid_is_ignored(tmp_path):
    (tmp_path / "instance.json").write_text(json.dumps({"pid": 2**22 + 12345, "port": 9}))
    claim = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    try:
        assert claim.kind == "owner"
    finally:
        claim.close()


def test_corrupt_instance_json_is_ignored(tmp_path):
    (tmp_path / "instance.json").write_text("{not json")
    claim = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    try:
        assert claim.kind == "owner"
    finally:
        claim.close()


def test_locked_but_not_serving_reports_busy(tmp_path):
    first = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    try:
        first.publish(54321)
        second = gui_app.claim_instance(tmp_path, probe=lambda url: False, wait=0.3, poll=0.05)
        assert second.kind == "busy"
    finally:
        first.close()


def test_second_claim_waits_for_a_starting_owner(tmp_path):
    """Owner holds the lock but publishes its port a moment later."""
    first = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=0)
    threading.Timer(0.3, lambda: first.publish(54321)).start()
    try:
        second = gui_app.claim_instance(tmp_path, probe=lambda url: True, wait=5, poll=0.05)
        assert second.kind == "existing"
        assert second.url.endswith(":54321/")
    finally:
        first.close()


def test_http_ok_true_only_for_200():
    app = _tiny_app()
    sock = gui_app.bind_socket(preferred=None)
    port = sock.getsockname()[1]
    handle = gui_app.start_server(app, sock, timeout=20)
    try:
        assert gui_app.http_ok(f"http://127.0.0.1:{port}/") is True
        assert gui_app.http_ok(f"http://127.0.0.1:{port}/missing") is False
    finally:
        handle.stop()
    assert gui_app.http_ok(f"http://127.0.0.1:{port}/") is False


# ── uvicorn thread ──────────────────────────────────────────────────────────


def test_start_server_serves_and_stop_releases_the_port():
    sock = gui_app.bind_socket(preferred=None)
    port = sock.getsockname()[1]
    handle = gui_app.start_server(_tiny_app(), sock, timeout=20)
    try:
        status, body = _get(f"http://127.0.0.1:{port}/")
        assert status == 200 and "圖層" in body
    finally:
        handle.stop()
    assert not handle.thread.is_alive()
    assert _port_free(port)


def test_start_server_times_out_with_clear_error():
    class NeverStarts:
        started = False
        should_exit = False

        async def serve(self, sockets=None):
            import asyncio

            while not self.should_exit:
                await asyncio.sleep(0.01)

    sock = gui_app.bind_socket(preferred=None)
    try:
        with pytest.raises(gui_app.ServerStartError):
            gui_app.start_server(
                _tiny_app(), sock, timeout=0.3, server_factory=lambda app, s: NeverStarts()
            )
    finally:
        sock.close()


def test_start_server_reports_a_server_that_died_on_startup():
    class Dies:
        started = False
        should_exit = False

        async def serve(self, sockets=None):
            raise RuntimeError("boom")

    sock = gui_app.bind_socket(preferred=None)
    try:
        with pytest.raises(gui_app.ServerStartError, match="boom"):
            gui_app.start_server(
                _tiny_app(), sock, timeout=5, server_factory=lambda app, s: Dies()
            )
    finally:
        sock.close()


# ── smoke output ────────────────────────────────────────────────────────────


def test_smoke_js_collects_every_required_field():
    js = gui_app.SMOKE_JS
    for needle in (
        "location.href", "documentElement.lang", "document.title", "__I18N__",
        "圖層", "childElementCount", "pywebview.api.open_url",
    ):
        assert needle in js
    assert "JSON.stringify" in js


def test_payload_from_html_mirrors_the_js_payload_keys():
    p = gui_app.payload_from_html("http://127.0.0.1:1/", PAGE)
    assert set(p) == {"url", "lang", "title", "hasI18N", "layers", "openUrlApi"}
    assert p["lang"] == "zh-Hant-TW"
    assert p["title"] == "Phoenix Intelligence Dashboard"
    assert p["hasI18N"] == 150
    assert p["layers"] is True
    q = gui_app.payload_from_html("u", "<html lang='en'><title>t</title></html>")
    assert (q["hasI18N"], q["layers"], q["lang"]) == (0, False, "en")


def test_write_smoke_result_is_complete_valid_json(tmp_path):
    out = tmp_path / "sub" / "out.json"
    gui_app.write_smoke_result(out, {"url": "x", "layers": True})
    assert json.loads(out.read_text()) == {"url": "x", "layers": True}
    assert not list(out.parent.glob("*.tmp"))


# ── main(): browser fallback ────────────────────────────────────────────────


@pytest.fixture
def gui_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv(gui_app.ENV_SMOKE_OUT, raising=False)
    monkeypatch.delenv(gui_app.ENV_FORCE_BROWSER, raising=False)
    monkeypatch.setattr(gui_app, "_load_app", _tiny_app)
    # never touch the real logging config / real browser / real dialogs
    monkeypatch.setattr(gui_app, "setup_logging", lambda *a: None)
    monkeypatch.setattr(gui_app, "show_error", lambda msg: None)
    return home


def test_main_force_browser_smoke_writes_payload_and_exits_zero(gui_env, tmp_path, monkeypatch):
    out = tmp_path / "smoke.json"
    monkeypatch.setenv(gui_app.ENV_SMOKE_OUT, str(out))
    monkeypatch.setenv(gui_app.ENV_FORCE_BROWSER, "1")
    opened: list[str] = []
    monkeypatch.setattr(gui_app.webbrowser, "open", lambda u, *a, **k: opened.append(u))
    assert gui_app.main() == 0
    data = json.loads(out.read_text())
    assert data["mode"] == "browser"
    assert data["url"].startswith("http://127.0.0.1:")
    assert data["lang"] == "zh-Hant-TW" and data["hasI18N"] == 150 and data["layers"] is True
    assert opened == []  # smoke runs must not pop real browser windows


def test_main_missing_webview_falls_back_to_browser(gui_env, tmp_path, monkeypatch):
    out = tmp_path / "smoke.json"
    monkeypatch.setenv(gui_app.ENV_SMOKE_OUT, str(out))
    monkeypatch.setitem(sys.modules, "webview", None)  # import -> ImportError
    assert gui_app.main() == 0
    assert json.loads(out.read_text())["mode"] == "browser"


def test_main_browser_fallback_opens_the_dashboard_url(gui_env, monkeypatch):
    monkeypatch.setenv(gui_app.ENV_FORCE_BROWSER, "1")
    opened: list[str] = []

    def fake_open(u, *a, **k):
        opened.append(u)

    monkeypatch.setattr(gui_app.webbrowser, "open", fake_open)
    # Stop the foreground wait immediately instead of blocking forever.
    monkeypatch.setattr(gui_app, "_wait_forever", lambda handle: None)
    assert gui_app.main() == 0
    assert len(opened) == 1 and opened[0].startswith("http://127.0.0.1:")


def test_main_second_instance_opens_existing_url_and_starts_no_server(gui_env, monkeypatch):
    first = gui_app.claim_instance(gui_app.support_dir(), probe=lambda u: True, wait=0)
    first.publish(54321)
    opened: list[str] = []
    monkeypatch.setattr(gui_app.webbrowser, "open", lambda u, *a, **k: opened.append(u))
    monkeypatch.setattr(gui_app, "http_ok", lambda url, timeout=2.0: True)
    started: list[int] = []
    monkeypatch.setattr(gui_app, "start_server", lambda *a, **k: started.append(1))
    try:
        assert gui_app.main() == 0
    finally:
        first.close()
    assert opened == ["http://127.0.0.1:54321/"]
    assert started == []


def test_main_smoke_mode_skips_the_single_instance_lock(gui_env, tmp_path, monkeypatch):
    first = gui_app.claim_instance(gui_app.support_dir(), probe=lambda u: True, wait=0)
    first.publish(54321)
    out = tmp_path / "smoke.json"
    monkeypatch.setenv(gui_app.ENV_SMOKE_OUT, str(out))
    monkeypatch.setenv(gui_app.ENV_FORCE_BROWSER, "1")
    try:
        assert gui_app.main() == 0
    finally:
        first.close()
    assert out.exists()


def test_main_server_start_failure_shows_error_and_returns_nonzero(gui_env, monkeypatch):
    shown: list[str] = []
    monkeypatch.setattr(gui_app, "show_error", shown.append)

    def boom(*a, **k):
        raise gui_app.ServerStartError("no start")

    monkeypatch.setattr(gui_app, "start_server", boom)
    assert gui_app.main() == 1
    assert shown and "no start" in shown[0]


# ── main(): window path with a fake pywebview ───────────────────────────────


class _Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self


class _FakeWindow:
    def __init__(self, url, js_api, results):
        self.url = url
        self.js_api = js_api
        self.events = types.SimpleNamespace(loaded=_Event())
        self._results = results
        self.destroyed = False

    def evaluate_js(self, js):
        # A real page: answer with the payload computed from the served HTML.
        _, body = _get(self.url)
        payload = gui_app.payload_from_html(self.url, body)
        payload["openUrlApi"] = True  # a real window has the js_api bridge
        return json.dumps(payload)

    def destroy(self):
        self.destroyed = True


def _fake_webview(raise_on_start: Exception | None = None):
    mod = types.ModuleType("webview")
    mod.created = []
    mod.started = []

    def create_window(title, url, **kw):
        w = _FakeWindow(url, kw.get("js_api"), mod)
        w.title, w.kw = title, kw
        mod.created.append(w)
        return w

    def start(*a, **kw):
        mod.started.append(kw)
        if raise_on_start:
            raise raise_on_start
        w = mod.created[-1]
        for h in w.events.loaded.handlers:
            th = threading.Thread(target=h)
            th.start()
            th.join(10)

    mod.create_window = create_window
    mod.start = start
    return mod


def test_main_window_mode_creates_expected_window_and_writes_smoke(gui_env, tmp_path, monkeypatch):
    fake = _fake_webview()
    monkeypatch.setitem(sys.modules, "webview", fake)
    out = tmp_path / "smoke.json"
    monkeypatch.setenv(gui_app.ENV_SMOKE_OUT, str(out))
    assert gui_app.main() == 0
    (win,) = fake.created
    assert win.title == "World Intel · 世界情報"
    assert win.url.startswith("http://127.0.0.1:")
    assert win.kw["width"] == 1440 and win.kw["height"] == 900
    assert win.kw["min_size"] == (960, 600)
    assert isinstance(win.js_api, gui_app.Api)
    assert win.destroyed is True
    data = json.loads(out.read_text())
    assert data["mode"] == "window"
    assert data["lang"] == "zh-Hant-TW" and data["layers"] is True and data["hasI18N"] > 100
    assert data["openUrlApi"] is True


def test_main_window_start_exception_falls_back_to_browser(gui_env, tmp_path, monkeypatch):
    fake = _fake_webview(raise_on_start=RuntimeError("no WKWebView"))
    monkeypatch.setitem(sys.modules, "webview", fake)
    out = tmp_path / "smoke.json"
    monkeypatch.setenv(gui_app.ENV_SMOKE_OUT, str(out))
    assert gui_app.main() == 0
    assert json.loads(out.read_text())["mode"] == "browser"


def test_main_releases_the_instance_lock_after_window_closes(gui_env, monkeypatch):
    fake = _fake_webview()
    monkeypatch.setitem(sys.modules, "webview", fake)
    assert gui_app.main() == 0  # no smoke: window "closes" when start() returns
    again = gui_app.claim_instance(gui_app.support_dir(), probe=lambda u: False, wait=0)
    try:
        assert again.kind == "owner"
    finally:
        again.close()
