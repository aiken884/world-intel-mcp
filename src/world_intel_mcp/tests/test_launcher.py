import os
import subprocess
import sys

import pytest

from world_intel_mcp import launcher


@pytest.mark.parametrize(
    "args,lang,rest",
    [
        (["--lang", "en", "cli", "--help"], "en", ["cli", "--help"]),
        (["--lang=zh-TW", "mcp"], "zh-TW", ["mcp"]),
        (["cli", "--lang", "en"], None, ["cli", "--lang", "en"]),  # 子指令之後原樣傳遞
        ([], None, []),
        (["--lang"], None, ["--lang"]),  # 缺值：原樣保留，之後以未知指令回報
    ],
)
def test_pop_lang(args, lang, rest):
    assert launcher.pop_lang(args) == (lang, rest)


def test_missing_lang_value_is_a_usage_error(capsys):
    assert launcher.main(["--lang"]) == 2
    assert "--lang" in capsys.readouterr().err


def test_unknown_subcommand_returns_2(capsys):
    assert launcher.main(["nope"]) == 2
    assert "nope" in capsys.readouterr().err


def test_dispatch_calls_target_with_remaining_args(monkeypatch):
    seen = {}

    def fake():
        seen["argv"] = list(sys.argv)

    monkeypatch.setitem(launcher._COMMANDS, "cli", fake)
    assert launcher.main(["--lang", "en", "cli", "markets", "--json-output"]) == 0
    assert seen["argv"][1:] == ["markets", "--json-output"]
    assert os.environ["WORLD_INTEL_LANG"] == "en"


def _run(args, lang_env=None):
    env = {k: v for k, v in os.environ.items() if k != "WORLD_INTEL_LANG"}
    if lang_env:
        env["WORLD_INTEL_LANG"] = lang_env
    return subprocess.run(
        [sys.executable, "-I", "-m", "world_intel_mcp.launcher", *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_help_default_is_chinese_and_lang_flag_wins_before_import():
    zh = _run(["cli", "--help"])
    assert "用法" in zh.stdout and "Usage:" not in zh.stdout
    en = _run(["--lang", "en", "cli", "--help"])
    assert "Usage:" in en.stdout and "用法" not in en.stdout


def test_top_level_usage_is_localized():
    assert "用法" in _run(["--help"]).stdout
    assert "Usage" in _run(["--lang", "en", "--help"]).stdout
