"""Click's own plural messages (ngettext) and lazily-imported modules.

The locale is pinned to English at import time by conftest, and the Click
patch is only installed when ``world_intel_mcp.cli`` is imported under a
non-English locale, so every check here runs in a fresh interpreter.
"""

import os
import subprocess
import sys

import pytest

# Builds a throwaway command that reaches every ngettext call site in
# click 8.5 and prints "CASE <name>" followed by the user-visible output.
_PROBE = r'''
import click
from click.testing import CliRunner
import world_intel_mcp.cli  # noqa: F401  (installs the translations)


@click.group()
def grp():
    pass


@grp.command()
@click.option("--pair", nargs=2, type=int)
@click.option("--one", type=click.Choice(["a"]))
@click.option("--pick", type=click.Choice(["a", "b"]))
@click.option("--when1", type=click.DateTime(formats=["%Y-%m-%d"]))
@click.option("--when2", type=click.DateTime(formats=["%Y-%m-%d", "%H:%M"]))
@click.option("--mod1")
@click.option("--mod2")
@click.option("--zebra")
def run(**kw):
    pass


@grp.command()
def noargs():
    pass


def case(name, args):
    r = CliRunner().invoke(grp, args)
    print("CASE", name)
    print(r.output)


case("opt_one_arg", ["run", "--zebra"])
case("opt_two_args", ["run", "--pair", "1"])
case("extra_one", ["noargs", "x"])
case("extra_many", ["noargs", "x", "y"])
case("choice_one", ["run", "--one", "z"])
case("choice_many", ["run", "--pick", "z"])
case("datetime_one", ["run", "--when1", "z"])
case("datetime_many", ["run", "--when2", "z"])
case("didyoumean_one", ["run", "--zebr", "x"])
case("didyoumean_many", ["run", "--mod3", "x"])

ctx = click.Context(run)
for label, n in (("one", 1), ("many", 3)):
    print("CASE takes_" + label)
    try:
        click.Option(["--p"], nargs=2).type_cast_value(ctx, tuple(range(n)))
    except click.BadParameter as e:
        print(e.message)
    print("CASE tuple_" + label)
    try:
        click.Tuple([int, int]).convert(tuple(range(n)), None, None)
    except click.BadParameter as e:
        print(e.message)
'''


def _probe(lang: str) -> dict[str, str]:
    env = {**os.environ, "WORLD_INTEL_LANG": lang, "COLUMNS": "200"}
    r = subprocess.run(
        [sys.executable, "-I", "-c", _PROBE],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    out: dict[str, str] = {}
    for block in r.stdout.split("CASE ")[1:]:
        name, _, body = block.partition("\n")
        out[name] = body
    return out


@pytest.fixture(scope="module")
def zh() -> dict[str, str]:
    return _probe("zh-TW")


@pytest.fixture(scope="module")
def en() -> dict[str, str]:
    return _probe("en")


# (case, expected Chinese fragment, English sentence that must be gone)
_ZH_CASES = [
    ("opt_one_arg", "選項 '--zebra' 需要一個引數。", "requires an argument"),
    ("opt_two_args", "選項 '--pair' 需要 2 個引數。", "requires 2 arguments"),
    ("extra_one", "收到非預期的額外引數（x）", "unexpected extra argument"),
    ("extra_many", "收到非預期的額外引數（x y）", "unexpected extra arguments"),
    ("choice_one", "'z' 不是 'a'。", "is not 'a'"),
    ("choice_many", "'z' 不是 'a', 'b' 其中之一。", "is not one of"),
    ("datetime_one", "'z' 不符合格式 '%Y-%m-%d'。", "does not match the format"),
    ("datetime_many", "'z' 不符合格式 '%Y-%m-%d', '%H:%M'。", "does not match the format"),
    ("didyoumean_one", "您是不是要輸入 '--zebra'？", "Did you mean"),
    ("didyoumean_many", "（您是不是要輸入以下其中之一：'--mod1', '--mod2'？）", "Did you mean"),
    ("takes_one", "需要 2 個值，但只給了 1 個。", "was given"),
    ("takes_many", "需要 2 個值，但給了 3 個。", "were given"),
    ("tuple_one", "需要 2 個值，但給了 1 個。", "values are required"),
    ("tuple_many", "需要 2 個值，但給了 3 個。", "values are required"),
]


@pytest.mark.parametrize("name,chinese,english", _ZH_CASES)
def test_plural_messages_are_chinese(zh, name, chinese, english):
    assert chinese in zh[name]
    assert english not in zh[name]


_EN_CASES = [
    ("opt_one_arg", "Option '--zebra' requires an argument."),
    ("opt_two_args", "Option '--pair' requires 2 arguments."),
    ("extra_one", "Got unexpected extra argument (x)"),
    ("extra_many", "Got unexpected extra arguments (x y)"),
    ("choice_one", "'z' is not 'a'."),
    ("choice_many", "'z' is not one of 'a', 'b'."),
    ("datetime_one", "'z' does not match the format '%Y-%m-%d'."),
    ("datetime_many", "'z' does not match the formats '%Y-%m-%d', '%H:%M'."),
    ("didyoumean_one", "Did you mean '--zebra'?"),
    ("didyoumean_many", "(Did you mean one of: '--mod1', '--mod2'?)"),
    ("takes_one", "Takes 2 values but 1 was given."),
    ("takes_many", "Takes 2 values but 3 were given."),
    ("tuple_one", "2 values are required, but 1 was given."),
    ("tuple_many", "2 values are required, but 3 were given."),
]


@pytest.mark.parametrize("name,english", _EN_CASES)
def test_english_is_untouched(en, name, english):
    assert english in en[name]


def _cli(args: list[str], lang: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "WORLD_INTEL_LANG": lang, "COLUMNS": "200"}
    return subprocess.run(
        [sys.executable, "-I", "-m", "world_intel_mcp.cli", *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


def test_real_cli_missing_option_value_is_chinese():
    r = _cli(["earthquakes", "--min-mag"], "zh-TW")
    assert r.returncode == 2
    assert "需要一個引數" in r.stderr
    assert "requires an argument" not in r.stderr


def test_real_cli_extra_argument_is_chinese():
    r = _cli(["earthquakes", "oops"], "zh-TW")
    assert r.returncode == 2
    assert "收到非預期的額外引數（oops）" in r.stderr
    assert "unexpected extra argument" not in r.stderr


def test_real_cli_invalid_choice_is_chinese():
    r = _cli(["news", "--category", "no-such-category"], "zh-TW")
    assert r.returncode == 2
    assert "其中之一" in r.stderr
    assert "is not one of" not in r.stderr


def test_real_cli_missing_required_options_is_chinese():
    r = _cli(["aoi", "define", "somewhere"], "zh-TW")
    assert r.returncode == 2
    assert "缺少選項" in r.stderr
    assert "Missing option" not in r.stderr


def test_real_cli_english_missing_option_value_unchanged():
    r = _cli(["earthquakes", "--min-mag"], "en")
    assert r.returncode == 2
    assert "requires an argument" in r.stderr


def test_shell_completion_module_is_translated_after_install():
    """click.shell_completion is imported lazily by Click; the installer must
    load it first so its ``_`` is rebound too."""
    script = (
        "import sys, gettext;"
        "import world_intel_mcp.cli;"
        "m = sys.modules.get('click.shell_completion');"
        "assert m is not None, 'not loaded';"
        "assert m._ is not gettext.gettext, 'not patched'"
    )
    env = {**os.environ, "WORLD_INTEL_LANG": "zh-TW"}
    r = subprocess.run(
        [sys.executable, "-I", "-c", script],
        capture_output=True, text=True, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
