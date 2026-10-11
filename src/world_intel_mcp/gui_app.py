"""World Intel.app entry point: the dashboard in a native window.

Not a Click command and it parses no command line.  Flow:

1. load ``~/Library/Application Support/World Intel/.env`` (never overrides
   variables that are already set);
2. take the single-instance lock (a second launch just opens the running
   instance in the browser and exits);
3. serve the Starlette dashboard with uvicorn on a free loopback port, in a
   daemon thread;
4. show it in a pywebview (WKWebView) window; closing the window ends the
   process.  If pywebview is unusable the dashboard URL is opened in the
   default browser instead and the process stays in the foreground.

Design notes
------------
* The port is picked by binding the listening socket ourselves and handing it
  to uvicorn, so there is no "find a free port, then race to bind it" window.
  A stable preferred port is tried first purely so the page origin (and with
  it localStorage: layer toggles, panel state) survives restarts; if it is
  taken we silently use any free port.  8501, the CLI dashboard's default,
  is never used.
* Single instance uses ``fcntl.flock`` on a lock file: the kernel drops the
  lock when the owner dies, so a crashed instance can never wedge a restart.
  ``instance.json`` (pid, port) only tells a second launch where to look.
* The only polling is bounded: waiting for ``uvicorn.Server.started`` and
  waiting for a starting-up peer to publish its port.  Neither has an event
  to wait on across thread / process boundaries.
"""

from __future__ import annotations

import asyncio
import fcntl
import json
import logging
import logging.handlers
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit

logger = logging.getLogger("world_intel_mcp.gui_app")

APP_NAME = "World Intel"
WINDOW_TITLE = "World Intel · 世界情報"
# Origin stability (localStorage).  Deliberately not 8501.
PREFERRED_PORT = 18501
ENV_SMOKE_OUT = "WORLD_INTEL_GUI_SMOKE_OUT"
ENV_FORCE_BROWSER = "WORLD_INTEL_GUI_FORCE_BROWSER"
SERVER_START_TIMEOUT = 30.0
_ERROR_TITLE = "World Intel · 世界情報"
_ERROR_PREFIX = "無法啟動 World Intel / World Intel failed to start\n\n"


# ── paths, logging, environment ─────────────────────────────────────────────


def support_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "Application Support" / APP_NAME


def log_dir(home: Path | None = None) -> Path:
    return (home or Path.home()) / "Library" / "Logs" / APP_NAME


def setup_logging(directory: Path | None = None) -> Path | None:  # pragma: no cover
    """Rotating file log (1 MB x 3).  A windowed app has no usable stdout."""
    try:
        directory = directory or log_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "world-intel.log"
        handler = logging.handlers.RotatingFileHandler(
            path, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root = logging.getLogger()
        root.addHandler(handler)
        root.setLevel(logging.INFO)
        # Per-request chatter would rotate real diagnostics out of 3 MB.
        for noisy in ("httpx", "httpcore", "world-intel-mcp"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

        def _hook(exc_type, exc, tb):
            logger.critical("uncaught exception", exc_info=(exc_type, exc, tb))

        sys.excepthook = _hook
        return path
    except OSError:
        return None


def load_user_env(directory: Path) -> bool:
    """Load ``<directory>/.env`` without overriding the real environment.

    A missing directory or file is not an error and nothing is created.
    """
    env_file = directory / ".env"
    if not env_file.is_file():
        return False
    from dotenv import load_dotenv

    return bool(load_dotenv(env_file, override=False))


# ── free port ───────────────────────────────────────────────────────────────


def bind_socket(preferred: int | None = PREFERRED_PORT) -> socket.socket:
    """A bound, listening loopback socket (to be handed to uvicorn as-is)."""
    candidates = [preferred] if preferred else []
    candidates.append(0)
    last: OSError | None = None
    for port in candidates:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Like uvicorn: TIME_WAIT leftovers of the previous run must not
        # block an immediate restart on the same (origin-stable) port.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.listen(128)
            return s
        except OSError as exc:
            s.close()
            last = exc
    raise last or OSError("cannot bind a loopback socket")  # pragma: no cover


# ── external links ──────────────────────────────────────────────────────────


def is_safe_external_url(url: Any) -> bool:
    """Only absolute http(s) URLs with a host may leave the app."""
    if not isinstance(url, str):
        return False
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    return parts.scheme.lower() in ("http", "https") and bool(parts.netloc)


class Api:
    """pywebview ``js_api``: everything public here is callable from the page."""

    def __init__(self, opener: Callable[[str], Any] | None = None) -> None:
        self._opener = opener

    def open_url(self, url: str) -> bool:
        if not is_safe_external_url(url):
            logger.warning("refused to open non-http(s) url: %r", url)
            return False
        (self._opener or webbrowser.open)(url.strip())
        return True


# ── single instance ─────────────────────────────────────────────────────────


def http_ok(url: str, timeout: float = 2.0) -> bool:
    """True iff GET url answers 200 (loopback only; proxies are bypassed)."""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(url, timeout=timeout) as resp:  # noqa: S310
            return resp.status == 200
    except Exception:
        return False


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_instance(directory: Path) -> dict | None:
    try:
        info = json.loads((directory / "instance.json").read_text())
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


class InstanceClaim:
    """Result of :func:`claim_instance`.

    ``kind`` is ``owner`` (we hold the lock and must serve), ``existing``
    (another instance is serving at ``url``) or ``busy`` (the lock is held but
    nothing answers).
    """

    def __init__(
        self, kind: str, directory: Path, fd: int | None = None, url: str | None = None
    ) -> None:
        self.kind = kind
        self.url = url
        self._dir = directory
        self._fd = fd

    def publish(self, port: int) -> None:
        tmp = self._dir / "instance.json.tmp"
        tmp.write_text(json.dumps({"pid": os.getpid(), "port": port}))
        os.replace(tmp, self._dir / "instance.json")

    def close(self) -> None:
        if self._fd is None:
            return
        info = _read_instance(self._dir)
        if info and info.get("pid") == os.getpid():
            try:
                (self._dir / "instance.json").unlink()
            except OSError:
                pass
        try:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
        finally:
            os.close(self._fd)
            self._fd = None


def claim_instance(
    directory: Path,
    probe: Callable[[str], bool] | None = None,
    wait: float = 10.0,
    poll: float = 0.2,
) -> InstanceClaim:
    probe = probe or http_ok
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(directory / "instance.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return InstanceClaim("owner", directory, fd=fd)
    except BlockingIOError:
        os.close(fd)
    deadline = time.monotonic() + wait
    while True:
        info = _read_instance(directory)
        if info and _pid_alive(info.get("pid")) and isinstance(info.get("port"), int):
            url = f"http://127.0.0.1:{info['port']}/"
            if probe(url):
                return InstanceClaim("existing", directory, url=url)
        if time.monotonic() >= deadline:
            return InstanceClaim("busy", directory)
        time.sleep(poll)


# ── uvicorn in a daemon thread ──────────────────────────────────────────────


class ServerStartError(RuntimeError):
    pass


class ServerHandle:
    def __init__(self, server: Any, thread: threading.Thread, sock: socket.socket) -> None:
        self.server = server
        self.thread = thread
        self.sock = sock

    @property
    def port(self) -> int:
        return self.sock.getsockname()[1]

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/"

    def stop(self, timeout: float = 5.0) -> None:
        self.server.should_exit = True
        self.thread.join(timeout)
        try:
            self.sock.close()
        except OSError:  # pragma: no cover
            pass


def _uvicorn_server(app: Any, sock: socket.socket) -> Any:
    import uvicorn

    # log_config=None: uvicorn's default dictConfig writes to stderr, which a
    # windowed app does not have; records propagate to our file handler.
    return uvicorn.Server(
        uvicorn.Config(
            app,
            log_level="warning",
            access_log=False,
            log_config=None,
            # Open SSE streams would otherwise hold shutdown until they end.
            timeout_graceful_shutdown=2,
        )
    )


def start_server(
    app: Any,
    sock: socket.socket,
    timeout: float = SERVER_START_TIMEOUT,
    server_factory: Callable[[Any, socket.socket], Any] | None = None,
) -> ServerHandle:
    server = (server_factory or _uvicorn_server)(app, sock)
    errors: list[BaseException] = []

    def runner() -> None:
        try:
            asyncio.run(server.serve(sockets=[sock]))
        except BaseException as exc:  # noqa: BLE001 - reported to the caller
            errors.append(exc)

    thread = threading.Thread(target=runner, name="world-intel-server", daemon=True)
    thread.start()
    deadline = time.monotonic() + timeout
    while not server.started:
        if not thread.is_alive():
            reason = repr(errors[0]) if errors else "exited without starting"
            raise ServerStartError(f"server stopped during startup: {reason}")
        if time.monotonic() >= deadline:
            server.should_exit = True
            thread.join(2.0)
            raise ServerStartError(f"server did not become ready within {timeout:g}s")
        time.sleep(0.05)
    return ServerHandle(server, thread, sock)


# ── smoke mode ──────────────────────────────────────────────────────────────

SMOKE_JS = (
    "JSON.stringify({"
    "url: location.href, "
    "lang: document.documentElement.lang, "
    "title: document.title, "
    "hasI18N: Object.keys(window.__I18N__ || {}).length, "
    "layers: !![...document.querySelectorAll('*')].find("
    "e => e.childElementCount === 0 && e.textContent.trim() === '圖層'), "
    "openUrlApi: !!(window.pywebview && window.pywebview.api "
    "&& typeof window.pywebview.api.open_url === 'function')"
    "})"
)


def payload_from_html(url: str, html: str) -> dict:
    """Same shape as ``SMOKE_JS`` but computed from the served HTML.

    Used only in the browser fallback (no DOM available).  The leaf-element
    check is approximated by: some msgid whose zh-TW value is 圖層 appears as
    the sole text of a tag in the raw HTML.
    """
    lang = re.search(r"<html[^>]*\blang=[\"']([^\"']*)[\"']", html)
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    catalog: dict = {}
    m = re.search(r"window\.__I18N__\s*=\s*(\{.*?\});</script>", html, re.S)
    if m:
        try:
            catalog = json.loads(m.group(1))
        except ValueError:
            catalog = {}
    keys = [k for k, v in catalog.items() if v == "圖層"] + ["圖層"]
    layers = any(re.search(r">\s*" + re.escape(k) + r"\s*<", html) for k in keys)
    return {
        "url": url,
        "lang": lang.group(1) if lang else "",
        "title": title.group(1).strip() if title else "",
        "hasI18N": len(catalog),
        "layers": layers,
        "openUrlApi": False,  # no pywebview bridge without a window
    }


def write_smoke_result(path: str | Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


# ── UI ──────────────────────────────────────────────────────────────────────


def show_error(message: str) -> None:  # pragma: no cover - needs a GUI session
    """Bilingual native error dialog (osascript; no extra dependency)."""
    text = (_ERROR_PREFIX + message).replace("\\", "\\\\").replace('"', '\\"')
    script = (
        f'display dialog "{text}" with title "{_ERROR_TITLE}" '
        'buttons {"OK"} default button "OK" with icon stop'
    )
    try:
        subprocess.run(["osascript", "-e", script], timeout=120, check=False)
    except Exception:
        logger.exception("could not show the error dialog")


def _load_app() -> Any:  # pragma: no cover - imports the whole dashboard
    from world_intel_mcp.dashboard.app import app

    return app


def _collect_window_payload(window: Any, settle: float = 10.0) -> dict:
    """Evaluate SMOKE_JS; the zh-TW translator and the pywebview bridge may
    need a moment after ``loaded``."""
    deadline = time.monotonic() + settle
    payload: dict = {}
    while True:
        payload = json.loads(window.evaluate_js(SMOKE_JS))
        if (payload.get("layers") and payload.get("openUrlApi")) or time.monotonic() >= deadline:
            return payload
        time.sleep(0.2)


def run_window(webview: Any, url: str, smoke_out: str | None, sdir: Path) -> None:
    """Show the dashboard in a native window; returns when it is closed."""
    window = webview.create_window(
        WINDOW_TITLE, url, js_api=Api(), width=1440, height=900, min_size=(960, 600)
    )
    if smoke_out:
        done = threading.Event()

        def on_loaded() -> None:
            if done.is_set():
                return
            done.set()
            try:
                payload = _collect_window_payload(window)
                payload["mode"] = "window"
            except Exception as exc:  # noqa: BLE001
                logger.exception("smoke evaluation failed")
                payload = {"mode": "window", "error": repr(exc)}
            try:
                write_smoke_result(smoke_out, payload)
            finally:
                window.destroy()

        window.events.loaded += on_loaded
    storage = sdir / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    webview.start(private_mode=False, storage_path=str(storage))


def _wait_forever(handle: ServerHandle) -> None:
    """Foreground until SIGTERM/SIGINT/server exit (browser fallback)."""

    def _stop(signum, frame):  # noqa: ARG001
        handle.server.should_exit = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(sig, _stop)
        except ValueError:  # pragma: no cover - not the main thread
            pass
    handle.thread.join()


def run_browser(handle: ServerHandle, smoke_out: str | None, reason: str) -> None:
    logger.warning("using the default browser instead of a window: %s", reason)
    if smoke_out:
        # No DOM here: derive the same fields from the served page, and do not
        # open real browser windows during automated verification.
        with urllib.request.urlopen(handle.url, timeout=10) as resp:  # noqa: S310
            html = resp.read().decode("utf-8", "replace")
        payload = payload_from_html(handle.url, html)
        payload["mode"] = "browser"
        write_smoke_result(smoke_out, payload)
        return
    webbrowser.open(handle.url)
    _wait_forever(handle)


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    smoke_out = os.environ.get(ENV_SMOKE_OUT) or None
    force_browser = bool(os.environ.get(ENV_FORCE_BROWSER))
    setup_logging()
    sdir = support_dir()
    logger.info("starting (smoke=%s force_browser=%s)", bool(smoke_out), force_browser)
    load_user_env(sdir)

    claim: InstanceClaim | None = None
    handle: ServerHandle | None = None
    try:
        if not smoke_out:
            claim = claim_instance(sdir)
            if claim.kind == "existing":
                logger.info("already running at %s; opening it", claim.url)
                webbrowser.open(claim.url)
                return 0
            if claim.kind == "busy":
                show_error(
                    "另一個 World Intel 正在啟動但沒有回應。/ "
                    "Another World Intel is starting but not responding."
                )
                return 1

        try:
            sock = bind_socket()
            handle = start_server(_load_app(), sock)
        except Exception as exc:  # noqa: BLE001
            logger.exception("could not start the dashboard server")
            show_error(str(exc))
            return 1
        logger.info("dashboard serving at %s", handle.url)
        if claim is not None:
            claim.publish(handle.port)

        webview: Any = None
        reason = f"forced by {ENV_FORCE_BROWSER}"
        if not force_browser:
            try:
                import webview  # pywebview; optional extra "gui"
            except Exception as exc:  # noqa: BLE001
                reason = f"pywebview unavailable: {exc!r}"
        if webview is None or force_browser:
            run_browser(handle, smoke_out, reason)
            return 0
        try:
            run_window(webview, handle.url, smoke_out, sdir)
        except Exception as exc:  # noqa: BLE001
            logger.exception("window failed")
            run_browser(handle, smoke_out, f"window failed: {exc!r}")
        return 0
    finally:
        if handle is not None:
            handle.stop()
        if claim is not None:
            claim.close()
        logger.info("exit")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
