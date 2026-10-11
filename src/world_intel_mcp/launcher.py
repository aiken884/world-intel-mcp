"""world-intel: single entry point (used by the frozen macOS build).

    world-intel [--lang zh-TW|en] mcp | cli ... | dashboard ... | collector ...

--lang is read here, *before* any world_intel_mcp.cli import, because Click
evaluates command help at import time.
"""

import os
import sys
from typing import Callable

from .i18n import t


def pop_lang(args: list[str]) -> tuple[str | None, list[str]]:
    """Strip a leading ``--lang X`` / ``--lang=X`` (only before the subcommand)."""
    if args and args[0] == "--lang" and len(args) >= 2:
        return args[1], args[2:]
    if args and args[0].startswith("--lang="):
        return args[0].split("=", 1)[1], args[1:]
    return None, args


def _run_mcp() -> None:
    from .server import run

    run()


def _run_cli() -> None:
    from .cli import main

    main()


def _run_dashboard() -> None:
    from .dashboard.app import run

    run()


def _run_collector() -> None:
    from .collector import main

    main()


_COMMANDS: dict[str, Callable[[], None]] = {
    "mcp": _run_mcp,
    "cli": _run_cli,
    "dashboard": _run_dashboard,
    "collector": _run_collector,
}


def _usage() -> str:
    return t(
        "Usage: world-intel [--lang zh-TW|en] <mcp|cli|dashboard|collector> [args...]\n"
        "  mcp        MCP stdio server (for Claude Code / Cursor)\n"
        "  cli        Command-line tool (same as `intel`)\n"
        "  dashboard  Live web dashboard (default http://127.0.0.1:8501)\n"
        "  collector  Background data collector"
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    lang, args = pop_lang(args)
    if lang:
        os.environ["WORLD_INTEL_LANG"] = lang
    if not args or args[0] in {"-h", "--help"}:
        print(_usage())
        return 0
    name, rest = args[0], args[1:]
    target = _COMMANDS.get(name)
    if target is None:
        print(t("Unknown command: {name}", name=name), file=sys.stderr)
        print(_usage(), file=sys.stderr)
        return 2
    sys.argv = [f"world-intel {name}", *rest]
    target()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
