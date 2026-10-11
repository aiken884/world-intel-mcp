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
    ],
)
def test_pop_lang(args, lang, rest):
    assert launcher.pop_lang(args) == (lang, rest)


@pytest.mark.parametrize(
    "args",
    [
        ["--lang"],  # 後面沒有參數
        ["--lang="],  # 空值
        ["--lang", ""],
        ["--lang", "   ", "cli"],
        ["--lang", "--help"],  # 值以 - 開頭：其實是下一個旗標
        ["--lang", "-h", "cli"],
        ["--lang=--help"],
    ],
)
def test_pop_lang_missing_value_raises(args):
    with pytest.raises(launcher.LangUsageError):
        launcher.pop_lang(args)


@pytest.mark.parametrize(
    "args",
    [["--lang"], ["--lang="], ["--lang", "--help"], ["--lang", "", "cli"]],
)
def test_missing_lang_value_is_a_usage_error(args, capsys):
    assert launcher.main(args) == 2
    err = capsys.readouterr().err
    assert "--lang requires a value" in err
    assert "--lang zh-TW|en" in err
    assert "Unknown command" not in err


def test_missing_lang_value_message_is_localized(capsys, monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert launcher.main(["--lang"]) == 2
    err = capsys.readouterr().err
    assert "--lang 需要指定值" in err
    assert "--lang zh-TW|en" in err
    assert "--lang requires a value" not in err


def test_unsupported_lang_value_warns_and_runs_in_zh_tw(monkeypatch, capsys):
    seen = {}
    monkeypatch.setitem(
        launcher._COMMANDS, "cli", lambda: seen.update(lang=os.environ["WORLD_INTEL_LANG"])
    )
    assert launcher.main(["--lang", "fr", "cli"]) == 0
    err = capsys.readouterr().err
    assert err.count("\n") == 1  # 一行警告
    assert "不支援的 --lang 值 'fr'" in err
    assert "--lang zh-TW|en" in err
    assert seen["lang"] == "zh-TW"


def test_unsupported_lang_value_overrides_env(monkeypatch):
    """命令列優先於環境變數：--lang fr 不應沿用環境變數的 en。"""
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    monkeypatch.setitem(launcher._COMMANDS, "cli", lambda: None)
    launcher.main(["--lang", "fr", "cli"])
    assert os.environ["WORLD_INTEL_LANG"] == "zh-TW"


@pytest.mark.parametrize("value", ["en_US.UTF-8", "zh-TW", "EN"])
def test_valid_lang_value_is_written_verbatim_without_warning(value, monkeypatch, capsys):
    monkeypatch.setitem(launcher._COMMANDS, "cli", lambda: None)
    assert launcher.main(["--lang", value, "cli"]) == 0
    assert capsys.readouterr().err == ""
    assert os.environ["WORLD_INTEL_LANG"] == value


def test_lang_flag_wins_over_env_without_env_warning(monkeypatch, capsys):
    monkeypatch.setenv("WORLD_INTEL_LANG", "fr")  # 異常環境值，但被旗標覆蓋
    monkeypatch.setitem(launcher._COMMANDS, "cli", lambda: None)
    assert launcher.main(["--lang", "en", "cli"]) == 0
    assert capsys.readouterr().err == ""
    assert os.environ["WORLD_INTEL_LANG"] == "en"


def test_bad_env_value_warns_once_in_launcher(monkeypatch, capsys):
    monkeypatch.setenv("WORLD_INTEL_LANG", "fr")
    monkeypatch.setitem(launcher._COMMANDS, "cli", lambda: None)
    assert launcher.main(["cli"]) == 0
    err = capsys.readouterr().err
    assert err.count("\n") == 1
    assert "不支援的 WORLD_INTEL_LANG 值 'fr'" in err
    assert "可用值：zh-TW、en" in err


@pytest.mark.parametrize("value", ["", "   ", "en", "zh_TW.UTF-8"])
def test_blank_or_valid_env_value_is_silent(value, monkeypatch, capsys):
    monkeypatch.setenv("WORLD_INTEL_LANG", value)
    monkeypatch.setitem(launcher._COMMANDS, "cli", lambda: None)
    assert launcher.main(["cli"]) == 0
    assert capsys.readouterr().err == ""


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


def test_subprocess_missing_lang_value_exit_2_and_message():
    r = _run(["--lang"])
    assert r.returncode == 2
    assert "--lang 需要指定值" in r.stderr
    assert "Unknown command" not in r.stderr and "未知的指令" not in r.stderr


def test_subprocess_unsupported_lang_warns_then_runs_chinese():
    r = _run(["--lang", "fr", "cli", "--help"])
    assert r.returncode == 0
    assert "不支援的 --lang 值 'fr'" in r.stderr
    assert "用法" in r.stdout
