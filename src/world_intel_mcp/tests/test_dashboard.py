"""Tests for dashboard runner configuration."""

import pytest

from world_intel_mcp.dashboard.app import _parse_run_args


def test_parse_run_args_port() -> None:
    host, port = _parse_run_args(["--port", "8765"])

    assert host == "127.0.0.1"
    assert port == 8765


def test_parse_run_args_host_and_port() -> None:
    host, port = _parse_run_args(["--host", "0.0.0.0", "--port", "9000"])

    assert host == "0.0.0.0"
    assert port == 9000


def test_parse_run_args_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("WORLD_INTEL_DASHBOARD_PORT", "7777")

    host, port = _parse_run_args([])

    assert host == "0.0.0.0"
    assert port == 7777


def _index_body(monkeypatch: pytest.MonkeyPatch, lang: str) -> str:
    from starlette.testclient import TestClient

    from world_intel_mcp.dashboard.app import app

    monkeypatch.setenv("WORLD_INTEL_LANG", lang)
    # No context manager: lifespan (default-path Cache) must not run.
    return TestClient(app).get("/").text


def test_index_is_served_in_zh_tw(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _index_body(monkeypatch, "zh-TW")

    assert '<html lang="zh-Hant-TW">' in body
    assert "window.__I18N__ = {" in body
    assert '"LAYERS": "圖層"' in body or '"LAYERS":"圖層"' in body
    # catalog is injected before the main script runs
    assert body.index("window.__I18N__") < body.index("var I18N = window.__I18N__")


def test_index_is_served_in_english(monkeypatch: pytest.MonkeyPatch) -> None:
    body = _index_body(monkeypatch, "en")

    assert '<html lang="en">' in body
    assert "window.__I18N__ = {};" in body


def test_index_script_has_translator_runtime() -> None:
    import world_intel_mcp.dashboard as pkg
    from pathlib import Path

    html = (Path(pkg.__file__).parent / "index.html").read_text(encoding="utf-8")
    assert "function _t(" in html
    assert "new MutationObserver" in html
