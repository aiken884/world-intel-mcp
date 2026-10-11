# zh-TW 預設語系 + macOS 本機執行檔 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讓 world-intel-mcp 的 CLI、儀表板、報告／摘要預設顯示台灣繁體中文，並能產出可在 Mac 直接執行的單一執行檔 `world-intel`。

**Architecture:** 以英文原句為 key 的輕量字串表（`i18n.t()`，查不到回傳原句）；CLI 用 `t()` 與 Click 說明後處理，儀表板由後端注入字典、前端 `_t()` + MutationObserver 即時替換文字節點，報告／摘要走 `t()`。打包用 PyInstaller onedir，入口為 `launcher.py` 分流 `mcp｜cli｜dashboard｜collector`。

**Tech Stack:** Python 3.12（建置用，專案下限 3.11）、Click 8 + Rich、Starlette/uvicorn、MCP stdio、pytest、PyInstaller、uv。

**Spec:** `docs/superpowers/specs/2026-10-11-zh-tw-locale-and-macos-binary-design.md`（含 PPLX 審查結論，執行者須一併閱讀）

## Global Constraints

- 預設語系 `zh-TW`；`WORLD_INTEL_LANG` 接受 `zh-TW`／`en`，其他值或空值回退 `zh-TW`。
- 不翻譯：外部 API 資料、MCP 工具 `description`／名稱／參數、JSON 輸出鍵名、股票代碼與機構名（SEC、USGS、ACLED 等）。
- 翻譯用語一律台灣用法，依 `src/world_intel_mcp/locales/GLOSSARY.md`；不得出現簡體專用字。
- 新依賴：零（執行檔建置除外，且僅裝在 `.venv-build/`）。
- 既有英文輸出斷言（~395 個）必須原封不動通過：測試環境一律釘 `WORLD_INTEL_LANG=en`。
- CI 覆蓋率下限 `--cov-fail-under=89` 不得降低。
- 不得 `--no-verify`、不得 push 到任何 remote（此 repo 為第三方開源專案，僅本機 commit）。
- 每個 commit 訊息結尾加兩行（空一行後）：
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`
  `Claude-Session: https://claude.ai/code/session_01EFM3FzYTQ1xZYQaudEcFta`
- 專案根目錄：`/Users/aikenlin/Projects/world-intel-mcp`（以下路徑皆相對於此）；所有 Python 指令用 `.venv/bin/python`。

## Review Focus

1. `WORLD_INTEL_LANG` 設成 `fr`、空字串、`EN`、`zh_TW`：不得拋例外；`EN`→英文、`zh_TW`→zh-TW、`fr`／空→zh-TW。（Task 1）
2. 遠端資料含 `{}`、`{0}`、`[red]`：經 `t(..., value=...)` 後逐字呈現，不被二次 format、不被 Rich 當標記。（Task 1、3）
3. 譯文漏寫／多寫 `{placeholder}`：執行期不崩潰（回退原句），且測試在建置期就擋下。（Task 1、2）
4. 字典值含 `</script>`、`&`、U+2028：注入儀表板後不得跳出 `<script>` 或破壞 JS。（Task 1、5）
5. 凍結執行檔在乾淨環境（`env -i`、臨時 HOME、非專案目錄）能啟動 MCP／儀表板／CLI，不依賴原始碼路徑與 `.env`。（Task 7）

---

## File Structure

| 檔案 | 責任 |
|---|---|
| `src/world_intel_mcp/i18n.py`（新） | `get_locale()`、`t()`、`placeholders()`、`render_dashboard_html()` |
| `src/world_intel_mcp/locales/__init__.py`（新） | 空檔，使 locales 成為套件 |
| `src/world_intel_mcp/locales/zh_TW.py`（新） | `CLICK`／`CLI`／`REPORTS`／`DASHBOARD` 四段字典與合併後的 `MESSAGES` |
| `src/world_intel_mcp/locales/GLOSSARY.md`（新） | 台灣用語對照與保留原文清單 |
| `src/world_intel_mcp/launcher.py`（新） | 單一入口與 `--lang` 前置解析 |
| `src/world_intel_mcp/cli.py`（改） | 說明後處理、表格欄名、`console.print` 文字、Click 內建字串 |
| `src/world_intel_mcp/reports.py`、`analysis/daily_digest.py`、`analysis/situation.py`（改） | 固定標題／提示語走 `t()` |
| `src/world_intel_mcp/dashboard/app.py`、`dashboard/index.html`（改） | 注入字典、前端 `_t()` 與 DOM 翻譯器 |
| `src/world_intel_mcp/tests/test_i18n.py`、`test_i18n_catalog.py`、`test_launcher.py`（新） | 對應測試 |
| `scripts/build-macos.sh`、`scripts/verify-macos-build.py`、`packaging/world_intel_entry.py`（新） | 建置與黑箱驗收 |
| `pyproject.toml`、`.gitignore`、`README.md`、`CHANGELOG.md`、`CLAUDE.md`（改） | entry point、忽略規則、文件 |

---

### Task 0: 開發環境與基準線

**Files:** 無程式變更

- [ ] **Step 1: 建立開發環境**

```bash
cd /Users/aikenlin/Projects/world-intel-mcp
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e ".[dev,dashboard]"
```
Expected: 安裝成功；`.venv/bin/python -c "import world_intel_mcp, mcp, starlette"` 無錯誤。

- [ ] **Step 2: 記錄基準線**

```bash
.venv/bin/python -m pytest -m "not smoke" --cov=world_intel_mcp -q 2>&1 | tail -15
```
Expected: 全綠；記下總測試數與覆蓋率（之後不得下降）。若有既有失敗，原樣記錄並回報，不得靜默忽略。

- [ ] **Step 3: 記下工具名稱基準（Task 7 驗收用）**

```bash
mkdir -p /private/tmp/claude-501/-Users-aikenlin-Projects-world-intel-mcp/1aa50ba1-9c0b-4e5b-938e-30db8aa54696/scratchpad
.venv/bin/python -c "import json; from world_intel_mcp.tools import ALL_TOOLS; print(json.dumps(sorted(t.name for t in ALL_TOOLS)))" \
  > /private/tmp/claude-501/-Users-aikenlin-Projects-world-intel-mcp/1aa50ba1-9c0b-4e5b-938e-30db8aa54696/scratchpad/expected-tools.json
.venv/bin/python -c "import json,sys; print(len(json.load(open(sys.argv[1]))))" /private/tmp/claude-501/-Users-aikenlin-Projects-world-intel-mcp/1aa50ba1-9c0b-4e5b-938e-30db8aa54696/scratchpad/expected-tools.json
```
Expected: 印出工具數（預期 132）。

---

### Task 1: i18n 核心模組與測試環境釘語系

**Files:**
- Create: `src/world_intel_mcp/i18n.py`, `src/world_intel_mcp/locales/__init__.py`, `src/world_intel_mcp/locales/zh_TW.py`
- Modify: `src/world_intel_mcp/tests/conftest.py`
- Test: `src/world_intel_mcp/tests/test_i18n.py`

**Interfaces:**
- Produces:
  - `get_locale() -> str`：回傳 `"zh-TW"` 或 `"en"`，每次呼叫都重讀環境變數（不快取）。
  - `t(msgid: str, **kwargs) -> str`
  - `placeholders(text: str) -> set[str]`
  - `get_catalog(locale: str | None = None) -> dict[str, str]`：完整 `MESSAGES`（en 回 `{}`）。
  - `get_dashboard_catalog(locale: str | None = None) -> dict[str, str]`：僅 `DASHBOARD` 段（en 回 `{}`）。
  - `render_dashboard_html(html: str) -> str`
  - `locales.zh_TW`：`CLICK`、`CLI`、`REPORTS`、`DASHBOARD`、`MESSAGES`（皆 `dict[str, str]`）。

- [ ] **Step 1: 寫失敗測試** — 建立 `src/world_intel_mcp/tests/test_i18n.py`

```python
"""i18n core: locale resolution, t() fallback/format safety, dashboard injection."""

import json

import pytest

from world_intel_mcp import i18n


@pytest.fixture
def fake_catalog(monkeypatch):
    cat = {
        "Hello {name}": "你好 {name}",
        "Total {n}": "總計 {n} 筆 {extra}",  # 譯文多出 placeholder -> 必須回退
        "Plain": "純文字",
    }
    monkeypatch.setattr(i18n, "_load_catalog", lambda locale: cat if locale == "zh-TW" else {})
    monkeypatch.setattr(i18n, "_load_dashboard_catalog", lambda locale: {"LAYERS": "圖層"} if locale == "zh-TW" else {})
    return cat


@pytest.mark.parametrize(
    "raw,expected",
    [(None, "zh-TW"), ("", "zh-TW"), ("   ", "zh-TW"), ("zh-TW", "zh-TW"), ("zh_TW", "zh-TW"),
     ("zh-Hant-TW", "zh-TW"), ("en", "en"), ("EN", "en"), ("en_US", "en"), ("fr", "zh-TW"), ("??", "zh-TW")],
)
def test_get_locale_resolution(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("WORLD_INTEL_LANG", raising=False)
    else:
        monkeypatch.setenv("WORLD_INTEL_LANG", raw)
    assert i18n.get_locale() == expected


def test_get_locale_is_not_cached(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert i18n.get_locale() == "en"
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.get_locale() == "zh-TW"


def test_t_translates_and_formats(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.t("Plain") == "純文字"
    assert i18n.t("Hello {name}", name="Aiken") == "你好 Aiken"


def test_t_missing_key_returns_msgid(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.t("Not in catalog") == "Not in catalog"
    assert i18n.t("Not {x}", x=1) == "Not 1"


def test_t_english_ignores_catalog(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert i18n.t("Plain") == "Plain"
    assert i18n.t("Hello {name}", name="A") == "Hello A"


def test_t_bad_translation_placeholder_falls_back_to_msgid(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    # 譯文含 {extra}，kwargs 沒給 -> KeyError -> 回退原句格式化
    assert i18n.t("Total {n}", n=5) == "Total 5"


def test_t_remote_values_are_not_reformatted(monkeypatch, fake_catalog):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    out = i18n.t("Hello {name}", name="{0}[red]{x}")
    assert out == "你好 {0}[red]{x}"


def test_placeholders():
    assert i18n.placeholders("a {x} b {y!r} {x}") == {"x", "y"}
    assert i18n.placeholders("no fields") == set()
    assert i18n.placeholders("{{literal}}") == set()


def test_get_catalog_by_locale(monkeypatch, fake_catalog):
    assert i18n.get_catalog("zh-TW") == fake_catalog
    assert i18n.get_catalog("en") == {}
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert i18n.get_dashboard_catalog() == {"LAYERS": "圖層"}


_HTML = '<html lang="en"><head><title>x</title></head><body><script src="a.js"></script><script>var a=1;</script></body></html>'


def test_render_dashboard_html_zh(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    monkeypatch.setattr(i18n, "_load_dashboard_catalog", lambda locale: {"LAYERS": "圖層", "x": "</script><b>& "})
    out = i18n.render_dashboard_html(_HTML)
    assert '<html lang="zh-Hant-TW">' in out
    assert out.count("window.__I18N__") == 1
    # 注入段在主 <script> 之前、且不含可跳出 script 的字元
    inject = out.split("window.__I18N__ = ", 1)[1].split(";</script>", 1)[0]
    assert "</script>" not in inject and "<" not in inject and " " not in inject
    assert json.loads(inject)["LAYERS"] == "圖層"
    assert json.loads(inject)["x"] == "</script><b>& "
    assert out.index("window.__I18N__") < out.index("var a=1;")


def test_render_dashboard_html_en(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    out = i18n.render_dashboard_html(_HTML)
    assert '<html lang="en">' in out
    assert "window.__I18N__ = {};" in out
```

- [ ] **Step 2: 確認失敗**

Run: `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n.py -q`
Expected: FAIL（`ImportError: cannot import name 'i18n'`）。

- [ ] **Step 3: 實作** — 建立 `src/world_intel_mcp/locales/__init__.py`（空檔）、`src/world_intel_mcp/locales/zh_TW.py`、`src/world_intel_mcp/i18n.py`

`locales/zh_TW.py`（先放種子，後續 task 擴充）：

```python
"""zh-TW (Taiwan Traditional Chinese) message catalog.

Keys are the exact English source strings. Terminology follows GLOSSARY.md.
Sections are merged into MESSAGES; a key may live in only one section.
"""

# Click's own help chrome ("Usage:", "Options:" ...) -- see cli.py.
CLICK: dict[str, str] = {}

# `intel` CLI: command help, table headers, console messages.
CLI: dict[str, str] = {}

# reports.py, daily digest, situation brief.
REPORTS: dict[str, str] = {}

# dashboard/index.html: static text, attributes and JS-built strings.
DASHBOARD: dict[str, str] = {}

MESSAGES: dict[str, str] = {**CLICK, **CLI, **REPORTS, **DASHBOARD}
```

`i18n.py`：

```python
"""Lightweight message catalog.

The msgid is the English source string; a missing translation falls back
to the msgid itself, so an untranslated string shows English instead of
breaking. The locale is re-read from WORLD_INTEL_LANG on every call.
"""

import json
import os
import string
from typing import Any

DEFAULT_LOCALE = "zh-TW"
_HTML_LANG = {"zh-TW": "zh-Hant-TW", "en": "en"}
_EN = {"en", "en-us", "en-gb"}
_ZH = {"zh", "zh-tw", "zh-hant", "zh-hant-tw"}


def get_locale() -> str:
    raw = os.environ.get("WORLD_INTEL_LANG", "").strip().replace("_", "-").lower()
    if raw in _EN:
        return "en"
    if raw in _ZH:
        return "zh-TW"
    return DEFAULT_LOCALE


def _load_catalog(locale: str) -> dict[str, str]:
    if locale == "zh-TW":
        from .locales.zh_TW import MESSAGES

        return MESSAGES
    return {}


def _load_dashboard_catalog(locale: str) -> dict[str, str]:
    if locale == "zh-TW":
        from .locales.zh_TW import DASHBOARD

        return DASHBOARD
    return {}


def get_catalog(locale: str | None = None) -> dict[str, str]:
    return _load_catalog(locale or get_locale())


def get_dashboard_catalog(locale: str | None = None) -> dict[str, str]:
    return _load_dashboard_catalog(locale or get_locale())


def placeholders(text: str) -> set[str]:
    return {field.split("!")[0].split(":")[0] for _, field, _, _ in string.Formatter().parse(text) if field}


def t(msgid: str, **kwargs: Any) -> str:
    """Translate *msgid*; apply ``str.format(**kwargs)`` if kwargs given.

    A translation whose placeholders do not match kwargs falls back to the
    English msgid so a bad catalog entry can never crash a command.
    """
    text = _load_catalog(get_locale()).get(msgid, msgid)
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        try:
            return msgid.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return msgid


def render_dashboard_html(html: str) -> str:
    """Set <html lang> and inject window.__I18N__ before the main script."""
    locale = get_locale()
    payload = json.dumps(_load_dashboard_catalog(locale), ensure_ascii=False, sort_keys=True)
    for ch, esc in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), (" ", "\\u2028"), (" ", "\\u2029")):
        payload = payload.replace(ch, esc)
    snippet = f"<script>window.__I18N__ = {payload};</script>\n"
    html = html.replace('<html lang="en">', f'<html lang="{_HTML_LANG[locale]}">', 1)
    return html.replace("<script>", snippet + "<script>", 1)
```

- [ ] **Step 4: 測試環境釘語系** — 修改 `src/world_intel_mcp/tests/conftest.py`：加入 `pytest_configure` hook（在收集測試模組、也就是 import `world_intel_mcp.cli` 之前執行，import 期的 Click 說明後處理才會讀到 `en`）：

```python
import os


def pytest_configure(config: pytest.Config) -> None:
    os.environ["WORLD_INTEL_LANG"] = "en"  # before any test module imports world_intel_mcp.cli
```

並在檔案內新增 autouse fixture：

```python
@pytest.fixture(autouse=True)
def _pin_english_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Existing assertions are English; zh-TW tests opt in via setenv."""
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
```

- [ ] **Step 5: 確認通過並跑全套**

Run: `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n.py -q && .venv/bin/python -m pytest -m "not smoke" -q 2>&1 | tail -3`
Expected: 新測試 PASS；全套與基準線相同。

- [ ] **Step 6: Commit** — `feat(i18n): add message catalog core and pin tests to en`（含 Global Constraints 的兩行結尾）

```bash
git add src/world_intel_mcp/i18n.py src/world_intel_mcp/locales src/world_intel_mcp/tests/conftest.py src/world_intel_mcp/tests/test_i18n.py
```

---

### Task 2: 字典完整性測試與用語表

**Files:**
- Create: `src/world_intel_mcp/tests/test_i18n_catalog.py`, `src/world_intel_mcp/locales/GLOSSARY.md`

**Interfaces:**
- Consumes: Task 1 的 `i18n.placeholders`、`locales.zh_TW`。
- Produces: 之後各 task「新增 `t()` 字串就必須補字典」的強制閘門；`collect_msgids()` 掃描函式（僅測試內使用）。

- [ ] **Step 1: 寫測試**

```python
"""Catalog integrity: every translatable literal has a zh-TW entry."""

import ast
import re
from html.parser import HTMLParser
from pathlib import Path

from world_intel_mcp import i18n
from world_intel_mcp.locales import zh_TW

PKG = Path(i18n.__file__).parent
INDEX_HTML = PKG / "dashboard" / "index.html"

# 簡體專用字（繁體不會用到）的最小防呆清單
_SIMPLIFIED = set("这个为从还会对话时间图层数据设备网络检测记录显示选项国际东西办开关态")
_SIMPLIFIED -= set("時間")  # 保險：確保不誤傷繁體字

_SKIP_DIRS = {"tests", "locales"}


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
    missing = {k: sorted(v) for k, v in collect_msgids().items() if k not in zh_TW.MESSAGES}
    assert not missing, "missing zh-TW entries:\n" + "\n".join(f"  {k!r}  <- {v}" for k, v in sorted(missing.items()))


def test_no_stale_keys_in_code_sections():
    used = set(collect_msgids())
    stale = {k for k in {**zh_TW.CLI, **zh_TW.REPORTS} if k not in used and k not in _DYNAMIC_KEYS}
    assert not stale, f"stale keys (not used by any t()): {sorted(stale)}"


def test_sections_do_not_overlap():
    total = len(zh_TW.CLICK) + len(zh_TW.CLI) + len(zh_TW.REPORTS) + len(zh_TW.DASHBOARD)
    assert len(zh_TW.MESSAGES) == total


def test_placeholders_match_between_msgid_and_translation():
    bad = {k: v for k, v in zh_TW.MESSAGES.items() if i18n.placeholders(k) != i18n.placeholders(v)}
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


# 不翻譯的專有名詞／品牌（需要時逐項加入並註明原因）
_DASHBOARD_UNTRANSLATED: set[str] = {"PHOENIX", "INTEL"}


def test_dashboard_static_text_is_translated():
    parser = _TextNodes()
    parser.feed(INDEX_HTML.read_text(encoding="utf-8"))
    needs = {
        s for s in parser.texts
        if re.search(r"[A-Za-z]{2,}", s) and s not in _DASHBOARD_UNTRANSLATED
    }
    missing = sorted(s for s in needs if s not in zh_TW.DASHBOARD)
    assert not missing, "dashboard text missing from DASHBOARD:\n" + "\n".join(f"  {s!r}" for s in missing)


# 以動態方式取用（非字面 t()）的 key：列在這裡才不會被判定為殘留
_DYNAMIC_KEYS: set[str] = set()
```

- [ ] **Step 2: 確認失敗／通過狀態**

Run: `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_catalog.py -q`
Expected: `test_dashboard_static_text_is_translated` FAIL（列出所有未翻的儀表板文字，這就是 Task 5 的工作清單）；其餘 PASS（目前還沒有 `t()` 呼叫）。這個失敗在 Task 5 前屬預期，**不要**用降低門檻或加白名單掩蓋；先以 `@pytest.mark.xfail(strict=True, reason="Task 5")` 標註該測試，Task 5 結束時移除。

- [ ] **Step 3: 建立用語表** — `src/world_intel_mcp/locales/GLOSSARY.md`

```markdown
# zh-TW 用語對照（台灣用法）

| English | 繁體中文（台灣） | 備註 |
|---|---|---|
| Dashboard | 儀表板 | 不用「仪表盘」「看板」 |
| Layers | 圖層 | |
| Geofence / AOI | 地理圍欄 | AOI＝關注區域（Area of Interest） |
| Circuit breaker | 斷路器 | |
| Source / Data source | 資料來源 | 不用「数据源」 |
| Cache | 快取 | 不用「缓存」 |
| Server | 伺服器 | 不用「服务器」 |
| Network | 網路 | 不用「网络」 |
| Default | 預設 | 不用「默认」 |
| Search | 搜尋 | 不用「搜索」 |
| Earthquake | 地震 | |
| Wildfire | 野火 | |
| Conflict | 衝突 | |
| Military | 軍事 | |
| Infrastructure | 基礎設施 | 不用「基础设施」 |
| Cyber threat | 網路威脅 | |
| Situation brief | 情勢簡報 | |
| Daily digest | 每日摘要 | |
| Alert | 警示 | |
| Loading | 載入中 | 不用「加载」 |
| Error | 錯誤 | 不用「错误」 |

保留原文：股票代碼、SEC／USGS／ACLED／NASA／GDELT 等機構與資料源名稱、Kp、M（規模）、BTC、VIX、DXY、Fear & Greed 等指標縮寫、品牌「Phoenix」。
```

- [ ] **Step 4: Commit** — `test(i18n): add catalog integrity gates and zh-TW glossary`

---

### Task 3: CLI 在地化

**Files:**
- Modify: `src/world_intel_mcp/cli.py`、`src/world_intel_mcp/locales/zh_TW.py`
- Test: `src/world_intel_mcp/tests/test_i18n_cli.py`（新）

**Interfaces:**
- Consumes: `i18n.t`、`i18n.get_locale`、`i18n.get_catalog`（Task 1）；完整性測試（Task 2）。
- Produces: `cli._Table`（`rich.table.Table` 子類，標題與欄名自動 `t()`）、`cli._localize_commands(group)`、`cli._install_click_translations()`。

- [ ] **Step 1: 寫失敗測試** — `src/world_intel_mcp/tests/test_i18n_cli.py`

```python
import os
import subprocess
import sys

import pytest


def _run(args, lang):
    env = {**os.environ, "WORLD_INTEL_LANG": lang}
    return subprocess.run(
        [sys.executable, "-I", "-m", "world_intel_mcp.cli", *args],
        capture_output=True, text=True, env=env, timeout=60,
    )


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
    from click.testing import CliRunner
    from world_intel_mcp import cli

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")

    async def fake(*_a, **_k):
        return {"quotes": [{"symbol": "TSTX", "price": 1234.5, "change_pct": 2.34, "currency": "USD"}]}

    monkeypatch.setattr(cli.markets, "fetch_market_quotes", fake)
    result = CliRunner().invoke(cli.main, ["markets"])
    assert result.exit_code == 0
    assert "TSTX" in result.output          # 股票代碼保留
    assert "代碼" in result.output           # "Symbol" 欄名已翻譯
    assert "Symbol" not in result.output


def test_remote_text_with_braces_and_markup_is_literal(monkeypatch):
    from click.testing import CliRunner
    from world_intel_mcp import cli

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")

    async def fake(*_a, **_k):
        return {"error": "bad {0} [red]boom[/red]"}

    monkeypatch.setattr(cli.markets, "fetch_market_quotes", fake)
    out = CliRunner().invoke(cli.main, ["markets"]).output
    assert "bad {0}" in out and "錯誤" in out
```

> 若 `cli.markets.fetch_market_quotes` 的實際函式名稱或回傳形狀不同，先讀 `cli.py:147-181` 與既有 `test_cli.py` 對 `markets` 的 mock 寫法，照同樣方式 patch；斷言內容（欄名「代碼」已翻、「Symbol」不再出現）不變。

- [ ] **Step 2: 確認失敗**

Run: `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_cli.py -q`
Expected: FAIL（說明仍為英文）。

- [ ] **Step 3: 實作 Click 說明與內建字串後處理** — 在 `cli.py` 的 import 區加入：

```python
from .i18n import get_locale, t
```

在 `cli.py` 檔案最底部、`if __name__ == "__main__":` 之前加入：

```python
def _localize_commands(group: click.Group) -> None:
    """Translate command/option help in place (Click reads docstrings once).

    The English original is kept on ``_wi_help_en`` so tests (and a second
    call) always see the msgid, never an already-translated string.
    """
    for cmd in group.commands.values():
        if cmd.help:
            cmd.help = t(cmd.__dict__.setdefault("_wi_help_en", cmd.help))
        if cmd.short_help:
            cmd.short_help = t(cmd.__dict__.setdefault("_wi_short_help_en", cmd.short_help))
        for param in cmd.params:
            if getattr(param, "help", None):
                param.help = t(param.__dict__.setdefault("_wi_help_en", param.help))
        if isinstance(cmd, click.Group):
            _localize_commands(cmd)


def _install_click_translations() -> None:
    """Route Click's own gettext strings ("Usage:", "Options:" ...) through t().

    Every click.* module does ``from gettext import gettext as _`` and looks
    ``_`` up as a module global at call time, so rebinding the global works.
    Scanning sys.modules (instead of a fixed module list) keeps this working
    across Click versions that move code between modules.
    """
    import gettext
    import sys

    for name, mod in list(sys.modules.items()):
        if not (name == "click" or name.startswith("click.")) or mod is None:
            continue
        original = getattr(mod, "_", None)
        if original is not gettext.gettext:
            continue

        def _wrap(message, _orig=original, **kw):
            translated = t(message)
            return translated if translated != message else _orig(message, **kw)

        mod._ = _wrap  # type: ignore[attr-defined]


if get_locale() != "en":
    _install_click_translations()
    main.help = t(main.help or "")
    for _p in main.params:
        if getattr(_p, "help", None):
            _p.help = t(_p.help)
    _localize_commands(main)
```

接著補 Click 內建字串的 msgid：先取得安裝版本實際字串，再填進 `locales/zh_TW.py` 的 `CLICK`。

```bash
.venv/bin/python - <<'EOF'
import re, pathlib, click
root = pathlib.Path(click.__file__).parent
seen = set()
for p in root.glob("*.py"):
    for m in re.finditer(r'_\(\s*"([^"]+)"', p.read_text()):
        seen.add(m.group(1))
for s in sorted(seen):
    print(repr(s))
EOF
```
將輸出中**使用者常見的**字串（`Usage:`、`Options:`、`Commands:`、`Show this message and exit.`、`Missing command.`、`No such command {name!r}.`、`No such option: {name}`、`Missing option '{name}'.`、`Error`、`Try '{command} {option}' for help.`、`Aborted!` 等）以 `CLICK = {...}` 填入，placeholder 與 Click 原文完全一致（例如 `"No such command {name!r}.": "沒有名為 {name!r} 的指令。"`）。

- [ ] **Step 4: 實作 Rich 表格子類並替換** — 在 `cli.py` 的 `_cell` 之後加入：

```python
class _Table(Table):
    """Rich Table whose title and column headers are translated."""

    def __init__(self, *args: Any, title: str | None = None, **kwargs: Any) -> None:
        super().__init__(*args, title=t(title) if title else None, **kwargs)

    def add_column(self, header: Any = "", *args: Any, **kwargs: Any):  # type: ignore[override]
        if isinstance(header, str) and header:
            header = t(header)
        return super().add_column(header, *args, **kwargs)
```

然後把 `cli.py` 內所有 `Table(` 建構呼叫改為 `_Table(`（`rg -n '\bTable\(' src/world_intel_mcp/cli.py`；`from rich.table import Table` 的 import 保留給子類）。

- [ ] **Step 5: 包裝 `console.print` 與提示文字（工作清單驅動）**

```bash
rg -n 'console\.print\(|\[(yellow|red|green|dim|bold)[^\]]*\][A-Z]' src/world_intel_mcp/cli.py
```
規則（逐筆套用，**只動固定的人類可讀英文**，遠端資料維持 `escape()`）：

```python
# 之前
console.print("[yellow]No market data available[/yellow]")
console.print(f"[red]Error:[/red] {escape(str(data['error']))}")
# 之後
console.print(f"[yellow]{t('No market data available')}[/yellow]")
console.print(f"[red]{t('Error:')}[/red] {escape(str(data['error']))}")
```
含變數的句子用具名 placeholder，值本身仍先 `escape()`：

```python
console.print(t("Showing {n} of {total}", n=len(rows), total=total))
```
`t()` 的 msgid 必須是**字面字串**（完整性測試靠 AST 掃描）；不得把 f-string 或變數傳給 `t()`。

- [ ] **Step 6: 補字典並迭代到綠燈**

```bash
.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_catalog.py -q 2>&1 | grep "<-"
```
輸出的每一行 `'msgid' <- file:line` 就是要補進 `locales/zh_TW.py`（`CLI`／`CLICK` 段）的 key；依 `GLOSSARY.md` 翻譯。另外補上所有 Click 指令說明與選項說明的 key，取得方式：

```bash
WORLD_INTEL_LANG=en .venv/bin/python - <<'EOF'
from world_intel_mcp import cli
import click
def walk(g):
    for c in g.commands.values():
        if c.help: print(repr(c.help))
        for p in c.params:
            if getattr(p, "help", None): print(repr(p.help))
        if isinstance(c, click.Group): walk(c)
walk(cli.main)
for p in cli.main.params:
    if getattr(p, "help", None): print(repr(p.help))
print(repr(cli.main.help))
EOF
```
將這些 msgid 全數加入 `CLI` 字典（`test_i18n_cli.py` 內新增一個測試，遍歷同一棵指令樹並斷言每個 `help` 都在 `zh_TW.MESSAGES` 中，防止日後新增指令漏翻）：

```python
def test_every_command_and_option_help_has_a_translation():
    import click
    from world_intel_mcp import cli
    from world_intel_mcp.locales import zh_TW

    missing = []
    def walk(g):
        for c in g.commands.values():
            texts = [c.__dict__.get("_wi_help_en", c.help)]
            texts += [p.__dict__.get("_wi_help_en", getattr(p, "help", None)) for p in c.params]
            for text in texts:
                if text and text not in zh_TW.MESSAGES:
                    missing.append(text)
            if isinstance(c, click.Group):
                walk(c)
    walk(cli.main)
    assert not missing, missing
```

- [ ] **Step 7: 全套測試**

Run: `.venv/bin/python -m pytest -m "not smoke" --cov=world_intel_mcp -q 2>&1 | tail -8`
Expected: 全綠；既有 `test_cli.py` 英文斷言不變；覆蓋率 ≥ 基準線。

- [ ] **Step 8: 手動內容檢查**

```bash
WORLD_INTEL_LANG=zh-TW .venv/bin/python -I -m world_intel_mcp.cli --help
WORLD_INTEL_LANG=zh-TW .venv/bin/python -I -m world_intel_mcp.cli earthquakes --help
```
Expected: 標題、說明、選項皆為繁體中文，無簡體字、無殘留英文說明句。

- [ ] **Step 9: Commit** — `feat(cli): zh-TW localization for help, tables and messages`

---

### Task 4: 報告、每日摘要、情勢簡報

**Files:**
- Modify: `src/world_intel_mcp/reports.py`、`src/world_intel_mcp/analysis/daily_digest.py`、`src/world_intel_mcp/analysis/situation.py`、`src/world_intel_mcp/locales/zh_TW.py`
- Test: `src/world_intel_mcp/tests/test_i18n_reports.py`（新）

**Interfaces:**
- Consumes: `i18n.t`、`i18n.get_locale`（Task 1）。
- Produces: 無新公開 API；`REPORTS` 字典段擴充。

- [ ] **Step 1: 確認沒有下游解析英文標題**

```bash
rg -n '"## Headlines|## Top Events|## Data Gaps|Executive Summary|Top Events by Domain|THREAT POSTURE' src --glob '!tests/**' --glob '!locales/**'
```
Expected: 只出現在產生處；若有任何程式「解析」這些英文標題（regex／split），先回報，不要直接改。

- [ ] **Step 2: 寫失敗測試** — `src/world_intel_mcp/tests/test_i18n_reports.py`

先讀既有 `test_daily_digest.py` 與 `test_reports.py` 的 fixture／mock 寫法（它們已有可重用的假資料與 patch），在同一風格下新增：

```python
import pytest


@pytest.mark.asyncio
async def test_daily_digest_markdown_headings_are_chinese(monkeypatch):
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    result = await _run_digest_with_stubbed_sources()  # 沿用 test_daily_digest.py 的 helper／mock
    md = result["markdown"]
    assert "每日情報摘要" in md
    assert "## 各領域重點事件" in md
    assert "## Top Events by Domain" not in md
    assert result["cited"] is True            # 引用機制不受語系影響
    assert "[1]" in md


def test_situation_prompt_requests_traditional_chinese_only_in_zh(monkeypatch):
    from world_intel_mcp.analysis import situation

    m = _sample_metrics()  # 沿用 test_analysis／test_situation 既有 metrics 樣本
    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    assert "Traditional Chinese" in situation._build_prompt(m, [])
    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    assert "Traditional Chinese" not in situation._build_prompt(m, [])


def test_fallback_brief_is_localized_and_cited(monkeypatch):
    from world_intel_mcp.analysis import situation

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    text = situation._fallback_brief(_sample_metrics(), {"posture": [1], "alerts": [1]})
    assert "威脅態勢" in text and "THREAT POSTURE" not in text
    assert "[1]" in text


def test_report_html_section_titles_are_chinese(monkeypatch):
    from world_intel_mcp import reports

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    html = _render_report_html_with_stub_data()  # 沿用 test_reports.py 的資料與 render 呼叫
    assert "<h2>執行摘要</h2>" in html
    assert "<h2>Executive Summary</h2>" not in html
    assert 'lang="zh-Hant-TW"' in html
```
`_run_digest_with_stubbed_sources`、`_sample_metrics`、`_render_report_html_with_stub_data` 是**指向既有測試 helper 的占位名稱**：實作時用 `rg -n "def test_|def _" src/world_intel_mcp/tests/test_daily_digest.py src/world_intel_mcp/tests/test_reports.py src/world_intel_mcp/tests/test_analysis.py` 找出對應 helper 並改成實際名稱（或把它們的建構程式碼複製進本檔）；斷言內容不變。

- [ ] **Step 3: 確認失敗**

Run: `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_reports.py -q`
Expected: FAIL（標題仍為英文）。

- [ ] **Step 4: 實作 daily_digest.py**

```python
# 檔案頂端
from ..i18n import t
```
標題改為（`"# Daily Intelligence Digest ({date})"` 這類含變數者用 placeholder）：

```python
md_parts = [t("# Daily Intelligence Digest ({date})", date=now.strftime("%Y-%m-%d")), ""]
md_parts.append(t("## Top Events by Domain"))
md_parts.append("\n".join(events_md) if events_md else t("_No current-event data available._"))
...
md_parts.append(t("## Headlines"))
md_parts.append(t("## Trends (6h vs. 48h baseline)"))
md_parts.append(t("## Timeline (last 24h)"))
md_parts.append(t("## Data Gaps"))
```
`_CURRENT_EVENT_DOMAINS` 的標籤（`"Earthquakes"`、`"Military aircraft"`…）在使用處以 `t(label)` 顯示；因 `t(label)` 的引數是變數，**這些 key 要列進** `test_i18n_catalog.py` 的 `_DYNAMIC_KEYS`，並在 `test_i18n_reports.py` 加一個測試：

```python
def test_digest_domain_labels_have_translations():
    from world_intel_mcp.analysis.daily_digest import _CURRENT_EVENT_DOMAINS
    from world_intel_mcp.locales.zh_TW import MESSAGES
    assert all(label in MESSAGES for label in _CURRENT_EVENT_DOMAINS.values())
```
內文裡的固定英文描述句（如 `"No data"`、各 domain 的趨勢句型）同樣改走 `t()`。

- [ ] **Step 5: 實作 situation.py** — `_build_prompt` 最後加語言指令（英文模式不變）：

```python
from ..i18n import get_locale, t

def _language_rule() -> str:
    if get_locale() == "zh-TW":
        return (
            "\nWrite the entire brief in Traditional Chinese as used in Taiwan (zh-TW). "
            "Keep citation markers exactly as [n]."
        )
    return ""
```
在 `_build_prompt` 回傳字串的結尾「`No preamble.`」之後串接 `+ _language_rule()`。`_fallback_brief` 內的 `THREAT POSTURE`、`MILITARY`、`CONFLICT`、`SEISMIC`、`FIRES`、`CYBER`、`HEALTH`、`SPACE`、`AIR TRAFFIC`、`CONGESTION` 與 `aircraft tracked` 等句型，改為 `t("THREAT POSTURE")` 等，含數字的句型用 placeholder。不得更動 `[n]` 引用的組裝邏輯（`_citation_suffix`）。

- [ ] **Step 6: 實作 reports.py** — 檔案頂端 `from .i18n import get_locale, t`；每個 `<h2>`、`<th>`、固定標籤與 `<html lang="en">` 都處理：

```python
sections_html.append(f"<h2>{t('Executive Summary')}</h2>{_render_situation_brief(data['world_brief'])}")
...
f'<html lang="{"zh-Hant-TW" if get_locale() == "zh-TW" else "en"}">'
```
工作清單：`rg -n '<h[1-3]>|<th>|<title>|class="label"|>[A-Z][a-z]+ ?[A-Za-z ]*<' src/world_intel_mcp/reports.py`。

- [ ] **Step 7: 補字典並迭代**

```bash
.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_catalog.py src/world_intel_mcp/tests/test_i18n_reports.py -q 2>&1 | grep "<-\|FAILED"
```
把缺的 key 補進 `REPORTS` 段，直到綠燈。

- [ ] **Step 8: 全套測試** — `.venv/bin/python -m pytest -m "not smoke" --cov=world_intel_mcp -q 2>&1 | tail -6`；Expected：全綠、覆蓋率不降。

- [ ] **Step 9: Commit** — `feat(reports): zh-TW localization for reports, digest and situation brief`

---

### Task 5: 儀表板

**Files:**
- Modify: `src/world_intel_mcp/dashboard/app.py`、`src/world_intel_mcp/dashboard/index.html`、`src/world_intel_mcp/locales/zh_TW.py`、`src/world_intel_mcp/tests/test_dashboard.py`
- Test: `src/world_intel_mcp/tests/test_i18n_catalog.py`（移除 Task 2 的 xfail）

**Interfaces:**
- Consumes: `i18n.render_dashboard_html`、`i18n.get_dashboard_catalog`（Task 1）。
- Produces: 前端全域 `window.__I18N__`、函式 `_t(msgid, vars)`；DOM 翻譯器（自動翻譯完整相符的文字節點與 `placeholder`／`title`／`aria-label`）。

- [ ] **Step 1: 後端測試** — 於 `src/world_intel_mcp/tests/test_dashboard.py` 追加（沿用該檔既有的 `TestClient` 匯入寫法）：

```python
def test_index_is_served_with_locale(monkeypatch):
    from starlette.testclient import TestClient
    from world_intel_mcp.dashboard.app import app

    monkeypatch.setenv("WORLD_INTEL_LANG", "zh-TW")
    body = TestClient(app).get("/").text
    assert '<html lang="zh-Hant-TW">' in body
    assert "window.__I18N__ = {" in body and '"LAYERS"' in body

    monkeypatch.setenv("WORLD_INTEL_LANG", "en")
    body = TestClient(app).get("/").text
    assert '<html lang="en">' in body
    assert "window.__I18N__ = {};" in body
```

- [ ] **Step 2: 確認失敗** — `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_dashboard.py -q`；Expected：FAIL。

- [ ] **Step 3: 後端注入** — `dashboard/app.py` 的 `index()`：

```python
from ..i18n import render_dashboard_html

async def index(request):
    """Serve the dashboard HTML page (reloads on each request during dev)."""
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(render_dashboard_html(html_path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: 前端執行期** — 在 `index.html` 主 `<script>` 的 `var $ = ...` 區塊之後、`// ════════════ STATE` 之前插入（先 `rg -n '\b_t\b|__I18N__' index.html` 確認名稱未被占用）：

```js
// ════════════ I18N ════════════
var I18N = window.__I18N__ || {};
var _hasOwn = Object.prototype.hasOwnProperty;
function _t(s, vars) {
    var r = _hasOwn.call(I18N, s) ? I18N[s] : s;
    if (vars) { r = r.replace(/\{(\w+)\}/g, function(m, k) { return vars[k] != null ? vars[k] : m; }); }
    return r;
}
(function () {
    if (!Object.keys(I18N).length) return;
    var ATTRS = ['placeholder', 'title', 'aria-label'];
    var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1 };
    var SKIP_CLASS = /\bleaflet-(tile|marker|shadow|overlay)-pane\b/;
    function text(node) {
        var raw = node.nodeValue, s = raw.trim();
        if (s && _hasOwn.call(I18N, s)) node.nodeValue = raw.replace(s, I18N[s]);
    }
    function attrs(el) {
        ATTRS.forEach(function (a) {
            var v = el.getAttribute && el.getAttribute(a);
            if (v && _hasOwn.call(I18N, v.trim())) el.setAttribute(a, I18N[v.trim()]);
        });
    }
    function walk(n) {
        if (n.nodeType === 3) { text(n); return; }
        if (n.nodeType !== 1 || SKIP[n.tagName]) return;
        if (n.className && typeof n.className === 'string' && SKIP_CLASS.test(n.className)) return;
        attrs(n);
        for (var c = n.firstChild; c; c = c.nextSibling) walk(c);
    }
    walk(document.documentElement);
    // Batch per animation frame; skip Leaflet's tile/marker/shadow/overlay panes
    // (high-churn, data-only). Popups and tooltips are still translated.
    var queue = [], scheduled = false;
    function flush() {
        scheduled = false;
        var items = queue; queue = [];
        items.forEach(function (m) {
            if (m.type === 'childList') { m.addedNodes.forEach(walk); }
            else if (m.type === 'characterData') { text(m.target); }
            else if (m.type === 'attributes') { attrs(m.target); }
        });
    }
    new MutationObserver(function (muts) {
        muts.forEach(function (m) { queue.push(m); });
        if (!scheduled) { scheduled = true; requestAnimationFrame(flush); }
    }).observe(document.documentElement, {
        childList: true, subtree: true, characterData: true,
        attributes: true, attributeFilter: ATTRS
    });
})();
```
譯文不在字典時原文保留，因此行為安全；替換後的中文不在字典中，不會造成無限觸發。

- [ ] **Step 5: 補字典（靜態文字）**

```bash
.venv/bin/python -m pytest src/world_intel_mcp/tests/test_i18n_catalog.py::test_dashboard_static_text_is_translated -q 2>&1 | grep "^  '"
```
把列出的每個字串補進 `DASHBOARD`（依 `GLOSSARY.md`；例：`"LAYERS": "圖層"`、`"Earthquakes": "地震"`、`"Military": "軍事"`、`"Conflict": "衝突"`、`"Wildfires": "野火"`、`"Nuclear Sites": "核設施"`、`"Infrastructure": "基礎設施"`、`"CONNECTING": "連線中"`、`"LIVE": "即時"`、`"RECONNECTING": "重新連線中"`、`"/ Search...": "/ 搜尋…"`、`"Semantic search...": "語意搜尋…"`、`"Search": "搜尋"`、`"Keyboard Shortcuts": "鍵盤快速鍵"`、`"Phoenix Intelligence Dashboard": "Phoenix 情報儀表板"`）。不翻的專有名詞才加進測試的 `_DASHBOARD_UNTRANSLATED`，並註明原因。接著移除 Task 2 加的 `xfail`。

- [ ] **Step 6: JS 動態拼接字串** — 找出「靜態節點翻譯器抓不到」的字串（文字與資料串接者）：

```bash
rg -n "' \+ |\+ '|textContent *= *'[A-Za-z]|\.title *= *'" src/world_intel_mcp/dashboard/index.html | rg -v "esc\(|safe\("
```
逐筆改為 `_t()`，例（取自實際程式碼）：

```js
// 之前
label.textContent = 'LOADING FEEDS ' + data._done + '/' + data._total;
$('#cntFires').title = (data.total_fires || total) + ' individual fire detections';
c.title = (data && data.error) || 'AOI fetch failed';
// 之後
label.textContent = _t('LOADING FEEDS {done}/{total}', {done: data._done, total: data._total});
$('#cntFires').title = _t('{n} individual fire detections', {n: data.total_fires || total});
c.title = (data && data.error) || _t('AOI fetch failed');
```
所有新 msgid 加入 `DASHBOARD`；placeholder 名稱與譯文一致（完整性測試會驗）。

- [ ] **Step 7: 實機檢視** — 啟動並用瀏覽器檢視（載入 `ego-browser` 或 `claude-in-chrome` skill）：

```bash
WORLD_INTEL_LANG=zh-TW .venv/bin/intel-dashboard --port 8599
```
開 `http://127.0.0.1:8599/`，截圖確認：頂列、圖層面板、各抽屜面板標題、搜尋框預設字、載入狀態皆為繁體中文；地圖與資料未壞；Console 無新增錯誤。將仍為英文的 UI 字串補進字典（資料內容本身維持英文屬正常）。

- [ ] **Step 7b: 效能檢查** — 在實機檢視時開啟瀏覽器效能面板（或 `console.time`），確認啟動後 30 秒內地圖互動（縮放、拖曳、圖層開關）無明顯卡頓；若翻譯器造成可感知延遲，縮小觀察範圍到 `#topBar`、`#layers`、抽屜與 popup 容器，不得退回「不翻譯」。

- [ ] **Step 8: 全套測試** — 同 Task 3 Step 7；Expected：全綠（含已移除 xfail 的靜態文字完整性測試）。

- [ ] **Step 9: Commit** — `feat(dashboard): zh-TW localization via injected catalog and DOM translator`

---

### Task 6: 單一入口 launcher

**Files:**
- Create: `src/world_intel_mcp/launcher.py`、`packaging/world_intel_entry.py`
- Modify: `pyproject.toml`、`src/world_intel_mcp/locales/zh_TW.py`
- Test: `src/world_intel_mcp/tests/test_launcher.py`

**Interfaces:**
- Consumes: `server.run`、`cli.main`、`dashboard.app.run`、`collector.main`、`i18n.t`。
- Produces: `launcher.main(argv: list[str] | None = None) -> int`；`launcher.pop_lang(args) -> tuple[str | None, list[str]]`（只處理子指令之前的 `--lang X`／`--lang=X`）；console script `world-intel`。

- [ ] **Step 1: 寫失敗測試** — `src/world_intel_mcp/tests/test_launcher.py`

```python
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
```

- [ ] **Step 2: 確認失敗** — `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_launcher.py -q`；Expected：FAIL（模組不存在）。

- [ ] **Step 3: 實作** — `src/world_intel_mcp/launcher.py`

```python
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
```

`packaging/world_intel_entry.py`：

```python
"""PyInstaller entry script (package-relative imports need a top-level file)."""

from world_intel_mcp.launcher import main

raise SystemExit(main())
```

`pyproject.toml` 的 `[project.scripts]` 加入一行：`world-intel = "world_intel_mcp.launcher:main"`。

- [ ] **Step 4: 補字典** — 於 `CLI` 段加入 `Usage: world-intel ...` 整段 msgid（與程式碼逐字相同，含 `\n`）與 `Unknown command: {name}` 的翻譯：

```python
"Unknown command: {name}": "未知的指令：{name}",
```
用法段譯文第一行以「用法：world-intel …」開頭（測試以「用法」判斷）。

- [ ] **Step 5: 通過與全套** — `.venv/bin/python -m pytest src/world_intel_mcp/tests/test_launcher.py src/world_intel_mcp/tests/test_i18n_catalog.py -q && .venv/bin/python -m pytest -m "not smoke" --cov=world_intel_mcp -q | tail -6`；Expected：全綠。

- [ ] **Step 6: Commit** — `feat(launcher): add world-intel single entry point with --lang`

---

### Task 7: macOS 執行檔建置與黑箱驗收

**Files:**
- Create: `scripts/build-macos.sh`、`scripts/verify-macos-build.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `packaging/world_intel_entry.py`（Task 6）、Task 0 記錄的 `expected-tools.json`。
- Produces: `dist/world-intel/world-intel`（onedir）；驗收腳本退出碼 0 = 全數內容檢查通過。

- [ ] **Step 1: 忽略規則** — `.gitignore` 追加兩行：`.venv-build/`、`*.spec`（`dist/`、`build/` 已在內）。

- [ ] **Step 2: 建置腳本** — `scripts/build-macos.sh`（`chmod +x`）

```bash
#!/usr/bin/env bash
# Build the macOS onedir executable: dist/world-intel/world-intel
# Usage: scripts/build-macos.sh   (requires uv; builds on this machine's arch)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VENV="$ROOT/.venv-build"
PYVER="${PYVER:-3.12}"

uv venv --python "$PYVER" "$VENV"
uv pip install --python "$VENV/bin/python" -e ".[dashboard]" pyinstaller

rm -rf "$ROOT/build" "$ROOT/dist"
"$VENV/bin/pyinstaller" \
  --noconfirm --clean --onedir \
  --name world-intel \
  --specpath "$ROOT/build" \
  --paths "$ROOT/src" \
  --collect-submodules world_intel_mcp \
  --collect-data world_intel_mcp \
  --collect-submodules mcp \
  --collect-submodules uvicorn \
  --collect-submodules starlette \
  --collect-submodules feedparser \
  --hidden-import dotenv \
  --exclude-module fastembed \
  --exclude-module qdrant_client \
  --exclude-module weasyprint \
  --exclude-module world_intel_mcp.tests \
  "$ROOT/packaging/world_intel_entry.py"

echo "Built: $ROOT/dist/world-intel/world-intel"
file "$ROOT/dist/world-intel/world-intel"
```

- [ ] **Step 3: 黑箱驗收腳本** — `scripts/verify-macos-build.py`（僅標準庫；以 `python3 -I` 執行）

```python
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
```

- [ ] **Step 4: 建置**

```bash
cd /Users/aikenlin/Projects/world-intel-mcp && chmod +x scripts/build-macos.sh
set -o pipefail; scripts/build-macos.sh 2>&1 | tail -25; echo "build exit: ${PIPESTATUS[0]:-$?}"
```
同時檢查 `build/world-intel/warn-world-intel.txt` 中與 `world_intel_mcp`、`mcp`、`uvicorn`、`starlette` 有關的 missing module 警告；並確認 `dist/world-intel/_internal/world_intel_mcp/dashboard/index.html` 存在。
Expected：`Built: .../dist/world-intel/world-intel`，`file` 顯示 Mach-O 64-bit executable arm64。若出現 `ModuleNotFoundError`／缺資料檔，依 PyInstaller 警告（`build/world-intel/warn-world-intel.txt`）補 `--hidden-import` 或 `--collect-all <pkg>`，每次補完重建，並把最終旗標寫回腳本。

- [ ] **Step 5: 黑箱驗收**

```bash
cd /Users/aikenlin/Projects/world-intel-mcp && python3 -I scripts/verify-macos-build.py \
  --exe dist/world-intel/world-intel \
  --expected-tools /private/tmp/claude-501/-Users-aikenlin-Projects-world-intel-mcp/1aa50ba1-9c0b-4e5b-938e-30db8aa54696/scratchpad/expected-tools.json
```
Expected：全部 `PASS`、`0 failure(s)`。任何 FAIL 都要查根因修正後重建，不得改驗收條件遷就。

- [ ] **Step 6: 實際資料煙霧測試（需網路）**

```bash
cd /tmp && /Users/aikenlin/Projects/world-intel-mcp/dist/world-intel/world-intel cli earthquakes --min-mag 5.0 | head -20
```
Expected：繁體中文的表格欄名；若網路來源暫時失敗，應顯示中文錯誤行，而非當成「0 筆」。

- [ ] **Step 7: Commit** — `build(macos): add PyInstaller onedir build and black-box verifier`（不得提交 `dist/`、`build/`、`.venv-build/`）

---

### Task 8: 文件與最終驗證

**Files:**
- Modify: `README.md`、`CHANGELOG.md`、`CLAUDE.md`

- [ ] **Step 1: README** — 在「Quick Start」之後新增兩節，內容要點（實際撰寫完整文字，不得留占位）：
  - 「語系（Language）」：預設 zh-TW；`WORLD_INTEL_LANG=en` 或 `world-intel --lang en …` 切回英文；範圍（CLI／儀表板／報告與摘要）與不翻譯項目（外部資料、MCP 工具說明）。
  - 「macOS 執行檔」：`scripts/build-macos.sh` 用法；產物 `dist/world-intel/world-intel`；子指令；Claude Code MCP 設定範例（`{"mcpServers":{"world-intel-mcp":{"command":"/絕對路徑/dist/world-intel/world-intel","args":["mcp"]}}}`）；只對應建置機架構；未簽署、自建自用；不含 `[vector]`、`[pdf]`；儀表板 `.env` 在凍結版的行為（以 Task 7 實測結果為準如實寫）。

- [ ] **Step 2: CHANGELOG** — 於最上方新增 `## Unreleased`：新增 zh-TW 語系（預設）、`WORLD_INTEL_LANG`、`world-intel` 單一入口、macOS 建置腳本。

- [ ] **Step 3: CLAUDE.md** — 新增一節「Localization」：使用者可見的固定文字必須走 `i18n.t()`（msgid 為字面英文）；新增 `t()` 字串須同步補 `locales/zh_TW.py`，`test_i18n_catalog.py` 會擋；JS 端用 `_t()`；不得在 import 期呼叫 `t()`（Click 說明後處理除外）。

- [ ] **Step 4: 最終全套驗證**

```bash
cd /Users/aikenlin/Projects/world-intel-mcp
.venv/bin/python -m pytest -m "not smoke" --cov=world_intel_mcp --cov-fail-under=89 -q 2>&1 | tail -8
.venv/bin/python -m compileall -q src && echo compile-ok
python3 -I scripts/verify-macos-build.py --exe dist/world-intel/world-intel --expected-tools /private/tmp/claude-501/-Users-aikenlin-Projects-world-intel-mcp/1aa50ba1-9c0b-4e5b-938e-30db8aa54696/scratchpad/expected-tools.json | tail -4
git status --short | head
```
Expected：測試全綠且覆蓋率達標；`compile-ok`；驗收 0 failure；工作樹乾淨（僅有預期的未追蹤忽略項）。

- [ ] **Step 5: 用語審查（技術＋用詞）** — 把 `zh_TW.py` 內容送 PPLX 做台灣用語審查：

```bash
pplx --no-tools --tags "world-intel-mcp,zh-tw-review" -q "請以台灣繁體中文用語審查下列 UI 字串翻譯：指出陸式用語、簡體混入、不自然或歧義的譯法，條列『原句 → 建議』，無問題者不用列。$(cat src/world_intel_mcp/locales/zh_TW.py)"
```
採納合理建議並更新字典，重跑 Step 4 的測試。

- [ ] **Step 6: Commit** — `docs: document zh-TW locale and macOS executable`

- [ ] **Step 7: 整個分支的獨立審查** — 啟動一個全新的 reviewer subagent（只給它 `git diff origin/main...HEAD` 與規格路徑，不給結論），要求針對：字串漏翻、`t()` 誤用（變數當 msgid）、儀表板 XSS／注入、打包缺漏。依回報修正後再收尾。
