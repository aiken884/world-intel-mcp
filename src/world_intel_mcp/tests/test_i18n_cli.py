"""zh-TW localization of the `intel` CLI (help, tables, messages)."""

import os
import subprocess
import sys

import click
import pytest
from click.testing import CliRunner

from world_intel_mcp import cli
from world_intel_mcp.locales import zh_TW


@pytest.fixture(autouse=True)
def _cli_isolation(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORLD_INTEL_CACHE_DB", str(tmp_path / "cli-cache.db"))
    monkeypatch.setenv("COLUMNS", "200")
    monkeypatch.setattr(cli, "_fetcher", None)
    monkeypatch.setattr(cli, "_aoi_store", None, raising=False)


def _run(args, lang):
    env = {**os.environ, "WORLD_INTEL_LANG": lang}
    return subprocess.run(
        [sys.executable, "-I", "-m", "world_intel_mcp.cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=60,
    )


def _fake(payload):
    async def _f(*args, **kwargs):
        return payload

    return _f


def test_root_help_is_traditional_chinese_by_default():
    out = _run(["--help"], "zh-TW").stdout
    assert "用法" in out and "選項" in out and "指令" in out
    assert "Usage:" not in out and "Options:" not in out


def test_root_help_english_when_requested():
    out = _run(["--help"], "en").stdout
    assert "Usage:" in out and "Options:" in out and "Commands:" in out


def test_subcommand_help_is_translated():
    out = _run(["earthquakes", "--help"], "zh-TW").stdout
    assert "最小規模" in out  # --min-mag 的說明


def test_table_headers_and_messages_are_translated(monkeypatch):
    """Actual rendered output of `intel markets` (not just exit code)."""
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    quotes = {
        "quotes": [
            {"symbol": "TSTX", "price": 1234.5, "change_pct": 2.34, "currency": "USD"}
        ]
    }
    monkeypatch.setattr(cli.markets, "fetch_market_quotes", _fake(quotes))
    result = CliRunner().invoke(cli.main, ["markets"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "TSTX" in result.output  # 股票代碼保留
    assert "代碼" in result.output  # "Symbol" 欄名已翻譯
    assert "Symbol" not in result.output


def test_empty_message_is_translated(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    monkeypatch.setattr(cli.markets, "fetch_market_quotes", _fake({"quotes": []}))
    result = CliRunner().invoke(cli.main, ["markets"], catch_exceptions=False)
    assert "沒有可用的市場資料" in result.output
    assert "No market data available" not in result.output


def test_remote_text_with_braces_and_markup_is_literal(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    monkeypatch.setattr(
        cli.markets,
        "fetch_market_quotes",
        _fake({"error": "bad {0} [red]boom[/red]"}),
    )
    out = CliRunner().invoke(cli.main, ["markets"], catch_exceptions=False).output
    assert "bad {0}" in out and "錯誤" in out


def test_every_command_and_option_help_has_a_translation():
    missing = []

    def walk(g):
        for c in g.commands.values():
            texts = [c.__dict__.get("_wi_help_en", c.help)]
            texts += [
                p.__dict__.get("_wi_help_en", getattr(p, "help", None))
                for p in c.params
            ]
            for text in texts:
                if text and text not in zh_TW.MESSAGES:
                    missing.append(text)
            if isinstance(c, click.Group):
                walk(c)

    walk(cli.main)
    assert not missing, missing
