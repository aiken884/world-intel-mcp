# 設計規格：zh-TW 預設語系 + macOS 本機執行檔

日期：2026-10-11　狀態：設計已核准；PPLX 技術審查已併入（見末段）

## 目標

1. 新增**台灣式繁體中文（zh-TW）**語系，並設為**預設**；可用環境變數切回英文。
2. 產出可在 Mac 本機直接執行、不需自備 Python 環境的**單一執行檔 `world-intel`**。

## 範圍

納入：網頁儀表板、CLI（`intel`）輸出、報告／每日摘要模板與情勢簡報提示語。
不納入：外部 API 回傳的資料內容（新聞標題等）、132 個 MCP 工具的 `description`
（給 Claude 讀，維持英文以保選工具準確度）、MCP 工具名稱與參數、JSON 輸出的鍵名。

## 一、語系機制（輕量自建，零新依賴）

- 新增 `src/world_intel_mcp/i18n.py`：`t(msgid, **kwargs)`。
  - **以英文原句當 key**（gettext 風格 msgid）；查不到就回傳原句，因此漏翻只會顯示英文，不會壞。
  - `**kwargs` 以 `str.format` 套用在翻譯結果上，供含變數的句子使用。
  - `get_locale()`：讀環境變數 `WORLD_INTEL_LANG`，接受 `zh-TW`（預設）、`en`；其他值回退 `zh-TW`。
- 新增 `src/world_intel_mcp/locales/zh_TW.py`：`MESSAGES: dict[str, str]`（純 Python 字典，
  PyInstaller 以一般模組打包，不需處理 `.mo` 資料檔）。
- 新增 `src/world_intel_mcp/locales/GLOSSARY.md`：台灣用語對照（儀表板、地理圍欄、斷路器、資料來源…）
  與「保留原文」清單（股票代碼、SEC／USGS／ACLED 等機構名、Fear & Greed 等指標名）。

## 二、各介面套用方式

| 介面 | 做法 |
|---|---|
| CLI（`cli.py`） | Click `help=`、Rich 表格欄名、提示／錯誤訊息改走 `t()`。Click 的說明在 import 時求值，所以語系只由環境變數決定（`--lang` 由 launcher 在 import 前寫入環境變數）。 |
| 儀表板 | `app.py` 在回應 `index.html` 時注入 `window.__I18N__ = {...}`（僅 zh-TW 字典，英文時為空）與 `<html lang>`；前端新增小型 `t()`，JS 動態產生的字串走 `t()`，靜態文字節點與 `placeholder`／`title` 由載入時的 walker 依字典替換。 |
| 報告／摘要 | `reports.py` 的 `<h2>` 標題與 `daily_digest.py` 的 Markdown 標題走 `t()`；`situation.py` 的 Ollama 提示語在 zh-TW 時加入「以台灣繁體中文輸出」，備援（機械式摘要）文字同樣走 `t()`。 |

## 三、測試與品質把關

- `conftest.py` 新增 autouse fixture，預設把 `WORLD_INTEL_LANG` 釘為 `en`，保住既有 ~395 個英文輸出斷言。
- 新增 `tests/test_i18n.py`：
  - `t()` 的查詢、fallback、`format` 套用、環境變數解析（含非法值）。
  - **完整性測試**：以 `ast` 掃描程式碼中所有 `t("…")` 的字面值，要求每一筆都存在於 `zh_TW.MESSAGES`；
    同時列出字典內未被使用的 key（避免殘留）。
  - **儀表板完整性**：以 `html.parser` 取出 `index.html` 的文字節點與 `placeholder`／`title`，
    每一筆必須在字典內，或列在明確的白名單（符號、數字、專有名詞）。
  - zh-TW 輸出測試：斷言 `intel markets` 等指令、報告 HTML、每日摘要 Markdown 的**實際輸出內容**含中文標題。
  - 簡體字防呆：字典值不得含常見簡體專用字（以一份短清單檢查）。
- 既有 CI 覆蓋率下限（`--cov-fail-under=89`）不降；新模組須有對應測試。

## 四、macOS 執行檔

- 新增 `src/world_intel_mcp/launcher.py`，entry point `world-intel`，子指令：
  `mcp`（stdio MCP 伺服器）、`cli …`（轉給 `intel`）、`dashboard`、`collector`；
  全域 `--lang zh-TW|en` 於 import 前寫入 `WORLD_INTEL_LANG`。
- 新增 `scripts/build-macos.sh`：以 `uv` 建專用環境（Python 3.12，避開系統 3.14 的相容風險），
  安裝專案 + `[dashboard]` + PyInstaller，產出 **onedir** 至 `dist/world-intel/`。
  - 不用 onefile：MCP 為 stdio 常駐程序，onefile 每次啟動都要解壓縮。
  - 以 `--collect-submodules world_intel_mcp`（含 `sources.*`、`tools.*`、collector 的動態 import）
    與 `--collect-data world_intel_mcp`（含 `dashboard/index.html`）處理動態載入與資料檔。
  - 預設不含 `[vector]`（fastembed／ONNX，體積大）與 `[pdf]`（weasyprint 需 pango）；
    `intel report --format html` 仍可用。
- 在 README 增補「macOS 執行檔」與「語系」章節，含 Claude Code 的 MCP 設定範例
  （`command` 指向 `dist/world-intel/world-intel`，`args: ["mcp"]`）。

## 五、驗收標準（驗內容，不只驗 exit code）

1. `pytest -m "not smoke" --cov=world_intel_mcp --cov-fail-under=89` 全綠。
2. `dist/world-intel/world-intel cli --help` 輸出為繁體中文；加 `--lang en` 為英文。
3. `world-intel mcp` 經 stdio 送 `initialize` + `tools/list`，回傳工具數與原始碼註冊數一致（132）。
4. `world-intel dashboard --port N` 啟動後 `GET /`：含 `lang="zh-Hant-TW"` 與預期的中文面板標題；`GET /api/...` 可回 JSON。
5. 在**非專案目錄**執行（確認不依賴原始碼路徑與 `.env`）。

## 已知限制與風險

- 未簽署／未公證：僅供本機自建自用；若將檔案傳給他人，Gatekeeper 會攔，需另行簽署。
- 儀表板 `.env` 為「專案根目錄」載入；凍結後路徑語意不同，驗收時確認並在 README 註明。
- 情勢簡報的中文品質取決於使用者本機 Ollama 模型。
- 只翻譯程式內的固定文字；外部資料維持原文。

## PPLX 技術審查結論（2026-10-11，已併入上文規格）

採納：
- **launcher 時序**：`launcher.py` 不依賴 Click 解析 `--lang`，自行掃描 `sys.argv` 並於**延遲 import** 任何 `world_intel_mcp.cli`／`server` 之前寫入 `WORLD_INTEL_LANG`；驗收須涵蓋 `world-intel --lang en cli --help` 與 `world-intel cli --help`。
- **打包收集**：`--collect-submodules` 除專案套件外，另對 `mcp`、`uvicorn`、`starlette` 明列並以凍結執行檔實測（不只測開發環境）；collector 的動態 import 需逐來源實測。
- **驗收加強**：MCP 比對**工具名稱集合**（與原始碼註冊表相同），不只比數量；儀表板驗 `/`、至少一個 `/api/*`、靜態資源與頁面載入無錯誤。
- **i18n 格式安全**：測試要求原文與譯文的 `{placeholder}` 集合相同；`t()` 在 `format` 失敗時回退為原文格式化結果，不拋例外。
- **import 期語系固定**：不快取 import 期翻譯結果；語系切換測試用子程序（不同環境變數、不同載入順序）。
- **資源路徑**：凍結後以 `Path(__file__).parent` 搭配 `--collect-data` 實測，並在非專案目錄、乾淨環境（`env -i`）執行。
- **架構**：產物僅對應建置機架構（Apple Silicon arm64），於 README 註明。

不採納／已涵蓋：Gatekeeper——本機自建的檔案不帶隔離屬性，PyInstaller 於 arm64 會自動 ad-hoc 簽署，可直接執行；散布給他人才需另行簽署（已列為限制）。
