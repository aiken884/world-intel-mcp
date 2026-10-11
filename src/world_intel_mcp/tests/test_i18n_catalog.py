"""Catalog integrity: every translatable literal has a zh-TW entry."""

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

from world_intel_mcp import i18n
from world_intel_mcp.locales import zh_TW

PKG = Path(i18n.__file__).parent
INDEX_HTML = PKG / "dashboard" / "index.html"

# 簡體專用字（繁體不會用到）的最小防呆清單
_SIMPLIFIED = set("这个为从还会对话时间图层数据设备网络检测记录选项国际东办开关态")

_SKIP_DIRS = {"tests", "locales"}

# 以動態方式取用（非字面 t()）的 key：列在這裡才不會被判定為殘留
_DYNAMIC_KEYS: set[str] = set()

# 不翻譯的專有名詞／品牌（需要時逐項加入並註明原因）
_DASHBOARD_UNTRANSLATED: set[str] = {"PHOENIX", "INTEL"}


def _py_files():
    for p in PKG.rglob("*.py"):
        if not (set(p.relative_to(PKG).parts) & _SKIP_DIRS):
            yield p


def collect_msgids() -> dict[str, set[str]]:
    """Map msgid -> {file:line,...} for t("..."), add_column("..."), Table(title="...")."""
    found: dict[str, set[str]] = {}
    for path in _py_files():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            lit = None
            f = node.func
            if isinstance(f, ast.Name) and f.id == "t" and node.args:
                lit = node.args[0]
            elif isinstance(f, ast.Attribute) and f.attr == "add_column" and node.args:
                lit = node.args[0]
            elif isinstance(f, ast.Name) and f.id in {"Table", "_Table"}:
                for kw in node.keywords:
                    if kw.arg == "title":
                        lit = kw.value
            if isinstance(lit, ast.Constant) and isinstance(lit.value, str):
                found.setdefault(lit.value, set()).add(f"{path.name}:{node.lineno}")
    return found


def test_every_msgid_in_code_has_a_translation():
    missing = {
        k: sorted(v) for k, v in collect_msgids().items() if k not in zh_TW.MESSAGES
    }
    assert not missing, "missing zh-TW entries:\n" + "\n".join(
        f"  {k!r}  <- {v}" for k, v in sorted(missing.items())
    )


def test_no_stale_keys_in_code_sections():
    used = set(collect_msgids())
    stale = {
        k
        for k in {**zh_TW.CLI, **zh_TW.REPORTS}
        if k not in used and k not in _DYNAMIC_KEYS
    }
    assert not stale, f"stale keys (not used by any t()): {sorted(stale)}"


def test_sections_do_not_overlap():
    total = (
        len(zh_TW.CLICK) + len(zh_TW.CLI) + len(zh_TW.REPORTS) + len(zh_TW.DASHBOARD)
    )
    assert len(zh_TW.MESSAGES) == total


def test_placeholders_match_between_msgid_and_translation():
    bad = {
        k: v
        for k, v in zh_TW.MESSAGES.items()
        if i18n.placeholders(k) != i18n.placeholders(v)
    }
    assert not bad, f"placeholder mismatch: {bad}"


def test_no_simplified_characters_or_empty_values():
    for k, v in zh_TW.MESSAGES.items():
        assert v.strip(), f"empty translation for {k!r}"
        hits = _SIMPLIFIED & set(v)
        assert not hits, f"simplified chars {sorted(hits)} in {v!r}"


class _TextNodes(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts: set[str] = set()
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self._skip += 1
        for name, value in attrs:
            if name in {"placeholder", "title", "aria-label"} and value:
                self.texts.add(value.strip())

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.texts.add(data.strip())


@pytest.mark.xfail(strict=True, reason="Task 5: dashboard catalog not filled yet")
def test_dashboard_static_text_is_translated():
    parser = _TextNodes()
    parser.feed(INDEX_HTML.read_text(encoding="utf-8"))
    needs = {
        s
        for s in parser.texts
        if re.search(r"[A-Za-z]{2,}", s) and s not in _DASHBOARD_UNTRANSLATED
    }
    missing = sorted(s for s in needs if s not in zh_TW.DASHBOARD)
    assert not missing, "dashboard text missing from DASHBOARD:\n" + "\n".join(
        f"  {s!r}" for s in missing
    )
