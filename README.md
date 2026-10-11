![Phoenix Intelligence Dashboard](docs/dashboard.png)

# World Intelligence MCP Server

[![MCP](https://img.shields.io/badge/MCP-Compatible-blue)](https://modelcontextprotocol.io)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-green)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

Real-time global intelligence across **30+ domains** with **132 MCP tools**, a live ops-center dashboard, a CLI, and a **Qdrant vector store** for enterprise-grade semantic search across accumulated intelligence. All data comes from free, public APIs: no paid subscriptions required.

Built for AI agents that need world awareness: market conditions, geopolitical risk, military posture, supply chain disruptions, cyber threats, and more — all queryable via the Model Context Protocol. The vector store enables natural language queries like *"military activity near Taiwan"* or *"cyber threats targeting healthcare"* across all historical data.

---

## What You Get

| Domain | Tools | Data Sources |
|--------|-------|-------------|
| **Financial Markets** | 7 | Yahoo Finance, CoinGecko, Alternative.me, Mempool |
| **Forex & Currency** | 3 | ECB/Frankfurter (8 major pairs, timeseries, cross rates) |
| **Bonds & Yields** | 2 | FRED, Yahoo Finance (yield curve, bond ETFs, spread analysis) |
| **Earnings** | 2 | Yahoo Finance (mega-cap calendar, surprise history) |
| **SEC Filings** | 3 | SEC EDGAR (full-text search, company filings, 8-K material events) |
| **Company Enrichment** | 1 | Yahoo Finance + GDELT + SEC + GitHub (composite profile) |
| **Macro Composite** | 1 | Weighted 6-signal market verdict (Fear&Greed, VIX, sectors, DXY, BTC, yields) |
| **Economic Indicators** | 6 | AAA fuel prices, EIA energy, FRED macro, World Bank |
| **Central Banks** | 1 | 15 central bank policy rates |
| **BTC Technicals** | 1 | SMA 50/200, golden/death cross, Mayer Multiple |
| **Natural Disasters** | 2 | USGS earthquakes, NASA FIRMS wildfires |
| **Environmental** | 2 | NASA EONET, GDACS disaster alerts |
| **Climate** | 1 | Open-Meteo temperature/precipitation anomalies |
| **Conflict & Security** | 4 | ACLED events, UCDP, unrest detection, humanitarian data |
| **Military & Defense** | 6 | adsb.lol, OpenSky, hexdb.io, surge detection, theater posture, aircraft batch |
| **Infrastructure** | 5 | Cloudflare Radar, submarine cables, cascade analysis, cloud status, RIPEstat BGP/RPKI |
| **Maritime** | 2 | NGA navigation warnings, vessel snapshots |
| **Aviation** | 2 | FAA airport delays, domestic flight snapshot |
| **News & Media** | 3 | 119 RSS feeds (4-tier), GDELT, trending keywords |
| **Intelligence Analysis** | 8 | Signal convergence, focal points, instability index, risk scores, escalation |
| **NLP Intelligence** | 4 | Entity extraction, event classification, news clustering, keyword spikes |
| **Strategic Synthesis** | 4 | Strategic posture, world brief, fleet report, population exposure |
| **Geospatial** | 11 | Military bases, ports, pipelines, nuclear facilities, cables, datacenters, spaceports, minerals, exchanges, trade routes, cloud regions |
| **AI & Technology** | 4 | arXiv papers, HuggingFace models, Hacker News, GitHub trending |
| **Cyber Threats** | 1 | URLhaus, Feodotracker, CISA KEV, SANS |
| **Health** | 1 | WHO DON, ProMED, CIDRAP disease outbreaks |
| **Space Weather** | 1 | NOAA SWPC (Kp index, solar flares, alerts) |
| **Social & Sanctions** | 3 | Reddit velocity, OFAC SDN list, nuclear test site monitoring |
| **Country Intelligence** | 3 | Country brief, country stocks, financial centers |
| **Prediction Markets** | 1 | Polymarket event contracts |
| **Elections** | 1 | Global election calendar with risk scoring |
| **Displacement** | 1 | UNHCR refugee/IDP data |
| **Shipping** | 1 | Dry bulk shipping stress index |
| **Government** | 1 | USAspending.gov federal contracts |
| **Traffic** | 2 | Road traffic flow, real-time incidents |
| **Cross-Domain Alerts** | 2 | Alert digest, weekly trends |
| **Monitoring** | 2 | Webcams, server health/status |
| **Vector Search** | 5 | Qdrant semantic search, similarity, timeline, stats |
| **Cross-Domain Analytics** | 3 | Correlation, domain summary, trend detection |
| **Reports** | 1 | PDF/HTML multi-domain intelligence reports |
| **Daily Digest** | 1 | Cited markdown morning brief: top events, headlines, trends, and timeline |
| **AOI Geofences** | 10 | User-defined areas of interest in three shapes (circle, polygon, corridor): define/list/update/delete, a cited multi-domain brief, hotspot escalation scoring, and enter/leave change detection for a user's own area. News is scoped to the place the area sits in (OSM Nominatim reverse geocoding, no key), not to the area's name |
| **Severe Weather** | 2 | NWS active CAP alerts (US), Meteoalarm (39 EU countries) |
| **Space Launches** | 1 | Launch Library 2 upcoming launches |
| **Volcanoes** | 1 | Smithsonian GVP weekly activity report |
| **Tropical Cyclones** | 2 | NHC (Atlantic, E/C Pacific) + JTWC (NW Pacific, N Indian, S Hemisphere) |
| **Situation Brief** | 1 | Cited situational awareness brief over MCP: bounded server-side overview synthesized via local Ollama, with a mechanically-cited fallback |

**Total: 132 tools** across 30+ intelligence domains.

---

## Quick Start

### Install

```bash
git clone https://github.com/marc-shade/world-intel-mcp.git
cd world-intel-mcp
pip install -e .

# Optional extras
pip install -e ".[dashboard]"  # Live ops-center dashboard
pip install -e ".[vector]"     # Qdrant vector store + FastEmbed
pip install -e ".[dev]"        # pytest, respx, coverage
```

### Run as MCP Server

```bash
world-intel-mcp  # stdio mode for Claude Code, Cursor, etc.
```

### Claude Code Configuration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "world-intel-mcp": {
      "command": "world-intel-mcp"
    }
  }
}
```

### Dashboard

```bash
intel-dashboard              # http://localhost:8501
intel-dashboard --port 9000  # custom port
```

#### 底圖與授權（Basemap & licensing）

儀表板底圖使用 OpenStreetMap 標準圖磚（`tile.openstreetmap.org`），免金鑰，地圖右下角固定顯示「© OpenStreetMap contributors」出處標示。使用上受 [OSM 圖磚使用政策](https://operations.osmfoundation.org/policies/tiles/) 約束：僅限個人／小量使用、必須保留出處標示、請勿大量預抓圖磚。

- 斷網或圖磚載入失敗時，地圖仍會顯示標記與資料，只是沒有底圖。
- OSM 是淺色圖，儀表板以 CSS 濾鏡（只作用在圖磚層）轉為深色，不影響標記與叢集。
- 要換其他圖磚來源，只需修改 `src/world_intel_mcp/dashboard/index.html` 中 `initMap()` 內的 `L.tileLayer(...)` 一處（連同 `attribution` 文字）。

### PDF/HTML Reports

```bash
pip install -e ".[pdf]"      # requires: brew install pango (macOS)
intel report                 # full PDF report → ~/.cache/world-intel-mcp/
intel report --format html   # HTML (no native deps needed)
intel report -o brief.pdf    # custom output path
intel report -s markets,cyber,earthquakes  # select sections
```

Map-first ops center: Leaflet map with toggle-able layers (quakes, military, conflict, fires, convergence, nuclear, infrastructure, your AOI geofences with last-sweep counts), 47 live SSE feeds, HUD bar, glassmorphic panels, per-source circuit breaker health.

### CLI

```bash
intel markets              # stock indices
intel earthquakes --min-mag 5.0
intel status               # cache + circuit breaker health
```

---

## 語系（Language）

預設語系為台灣繁體中文（`zh-TW`）。要切回英文，可設定環境變數或在指令加旗標：

```bash
export WORLD_INTEL_LANG=en           # 環境變數
world-intel --lang en cli markets    # 單次指定；--lang 只能放在子指令之前
```

- 支援 `en*`、`zh*`，其他一律 zh-TW。只看第一段語言碼，並容忍 POSIX 寫法（例如 `en_US.UTF-8`、`en-AU`、`zh_TW.UTF-8`）；`zh-CN`、`zh-HK` 等沒有對應語系，視同 `zh-TW`；無法辨識的值（如 `fr`、`eng`）或空值回退為 `zh-TW`。
- 翻譯範圍：`intel` CLI（指令說明、表格欄名、訊息）、網頁儀表板，以及報告、每日摘要、情勢簡報的固定文字。情勢簡報使用 Ollama 時，zh-TW 會要求模型以台灣繁體中文輸出。
- 不翻譯：外部 API 回傳的資料（例如新聞標題）、MCP 工具名稱／說明／參數、JSON 輸出的鍵名、stderr 的 logger 訊息，以及儀表板與 collector 的 argparse 說明。

## macOS 執行檔

可把 MCP 伺服器、CLI、儀表板與 collector 打包成單一 macOS 執行檔（PyInstaller onedir），不需要在目標機器上維護 Python 環境。

```bash
scripts/build-macos.sh   # 需要 uv；在 .venv-build/ 以 Python 3.12 建置
```

產物為 `dist/world-intel/world-intel`（約 34 MB，Mach-O arm64）。單一入口 `world-intel` 的子指令：

- `mcp`：stdio MCP 伺服器
- `cli …`：同 `intel`
- `dashboard`：網頁儀表板
- `collector`：collector daemon

Claude Code 設定範例（路徑請換成實際的絕對路徑）：

```json
{
  "mcpServers": {
    "world-intel-mcp": {
      "command": "/絕對路徑/dist/world-intel/world-intel",
      "args": ["mcp"]
    }
  }
}
```

驗收可執行：先由原始碼的工具註冊表產生工具名稱清單，再讓驗收腳本比對執行檔實際對外的 MCP 工具名稱集合（內容比對，不只看結束碼）：

```bash
.venv/bin/python -c "import json;from world_intel_mcp.tools import ALL_TOOLS;print(json.dumps(sorted(x.name for x in ALL_TOOLS)))" > /tmp/expected-tools.json
python3 -I scripts/verify-macos-build.py --exe dist/world-intel/world-intel --expected-tools /tmp/expected-tools.json
```

`--expected-tools` 是必填參數，內容就是上面這份 JSON 陣列。腳本會在暫存目錄（獨立 HOME 與工作目錄）中檢查 `--help` 語系、MCP `tools/list` 與儀表板首頁；任何一項失敗時，會附上子程序 stderr 的最後約 40 行。

限制：

- 只對應建置機架構（Apple Silicon arm64）。
- 未簽署、未公證。本機自建自用不受 Gatekeeper 影響；若要傳給他人，需另行簽署。
- 不含 `[vector]`（fastembed／Qdrant）與 `[pdf]`（WeasyPrint）功能；`intel report --format html` 仍可用。
- 金鑰檔位置：凍結版的儀表板（`dashboard`）與 collector（`collector`）都只讀取執行檔旁的 `dist/world-intel/.env`（已用建置產物實測），不會讀取專案根目錄的 `.env`，也不會讀取 `dist/.env` 或 `dist/world-intel/_internal/.env`。金鑰請放在該處，或以環境變數提供。
- 重建（`scripts/build-macos.sh`）只會替換 `dist/world-intel/`（不動同在 `dist/` 下的 App 與 DMG），並會先備份、建置成功後還原 `dist/world-intel/.env`（權限保持不變），金鑰不會因重建而消失。

## macOS App（DMG）

給不想開終端機的使用者：雙擊 `World Intel.app`，就會開出一個原生視窗直接顯示儀表板（預設繁體中文），關閉視窗即結束程式。內部是 PyInstaller 打包的 Python 加上 pywebview（macOS 內建的 WKWebView），儀表板伺服器只監聽本機 `127.0.0.1`。

**建置**（需要 uv；Apple Silicon）：

```bash
scripts/build-macos-app.sh   # → dist/World Intel.app（約 50 MB，ad-hoc 簽署），用 .venv-app/ 建置
scripts/make-dmg.sh          # → dist/World-Intel-<版本>-arm64.dmg（約 29 MB，含 App 與 Applications 捷徑）
python3 -I scripts/verify-macos-app.py --app "dist/World Intel.app" --dmg dist/World-Intel-*-arm64.dmg
```

版本號取自 `pyproject.toml`。驗收腳本會實際啟動 App（乾淨環境、暫存 HOME），檢查頁面語系、翻譯字典與「圖層」標籤確實渲染、埠佔用時仍可啟動、單一實例、DMG 內容與從 DMG 複製出的 App，全部通過才回傳 0。

**安裝**：開啟 DMG，把 `World Intel` 拖曳到 `Applications` 捷徑，再從「應用程式」開啟。

**第一次開啟**：本機自己建置的 App 通常可直接開。從網路或他機取得的副本沒有公證，會被 Gatekeeper 擋下；請對 App 按右鍵 →「打開」，或執行下列指令移除隔離屬性（僅限你信任的來源）：

```bash
xattr -cr "/Applications/World Intel.app"
```

**設定與記錄**：

- API 金鑰：放在 `~/Library/Application Support/World Intel/.env`（格式同專案的 `.env`；目錄需自行建立，已存在於環境變數中的值不會被覆蓋）。
- 記錄檔：`~/Library/Logs/World Intel/world-intel.log`（1 MB × 3 份輪替）。
- 單一實例：重複開啟時，第二次只會用瀏覽器打開已在執行的那個實例然後結束。

**與 CLI 版（`dist/world-intel`）的差異**：App 只提供儀表板視窗，沒有 `mcp`／`cli`／`collector` 子指令，也不接受命令列參數；兩者可並存於 `dist/`。App 的金鑰檔位置與 CLI 版不同（見上）。若瀏覽器介面較合適，也可繼續用 CLI 版的 `dashboard` 子指令。

**已知限制**：

- 只對應建置機架構（Apple Silicon arm64）。
- 未簽署（僅 ad-hoc）、未公證；本機自用不受影響，轉給他人須參考上方「第一次開啟」。
- 不含 `[vector]`（fastembed／Qdrant）與 `[pdf]`（WeasyPrint）功能；儀表板的 PDF 報告端點因此不可用。
- 儀表板優先使用固定的本機埠 18501（讓視窗內的版面設定能跨次保留），被佔用時改用任一空埠；不使用 8501，不會與 CLI 版儀表板衝突。
- 圖示為占位圖（儀表板截圖的置中裁切，由 `packaging/make-icon.sh` 產生）。
- 若 pywebview 無法啟動，會退回用預設瀏覽器開啟儀表板並留在前景，原因寫在記錄檔。

---

## Architecture

```
server.py     (MCP stdio) ─┐                                               ┌─ VectorStore (Qdrant)
cli.py        (Click CLI)  ├─> sources/*.py ─> Fetcher ─> CircuitBreaker ─┤
dashboard.py  (SSE)        │    analysis/*.py                              └─ Cache (SQLite)
collector.py  (daemon)    ─┘
```

- **Fetcher**: Centralized async HTTP client (httpx). Retries, per-source rate limiting, stale-data fallback. Auto-stores results in vector store on fresh fetches.
- **CircuitBreaker**: Per-source tracking. 3 consecutive failures trips for 5 minutes. Each RSS feed gets its own breaker.
- **Cache**: SQLite WAL-mode TTL cache. `get()` returns live data, `get_stale()` returns expired data for fallback.
- **VectorStore**: Qdrant + FastEmbed (BAAI/bge-small-en-v1.5, 384-dim). Async background worker queue for non-blocking storage. Enables semantic search across all accumulated intelligence.
- **Collector**: Standalone daemon that fetches all 51 sources in parallel and populates the vector store. Run once or as a daemon (default: 5-minute interval). Includes the AOI change sweep, so a running daemon continuously watches every defined geofence.
- **Sources** (`sources/*.py`): 30+ modules, each exports `async def fetch_*(fetcher, **kwargs) -> dict`.
- **Analysis** (`analysis/*.py`): Cross-domain synthesis — signal aggregation, instability indexing, NLP, company enrichment, macro composite.
- **Config** (`config/*.py`): Curated datasets — 22 hotspots, 70+ bases, 40 ports, 24 pipelines, 24 nuclear facilities, 34 cables, 48 datacenters, 27 spaceports, 82 exchanges.

---

## MCP Tools Reference

### Financial Markets (7)
| Tool | Description |
|------|-------------|
| `intel_market_quotes` | Stock index quotes (S&P 500, Dow, Nasdaq, FTSE, Nikkei) |
| `intel_crypto_quotes` | Top crypto prices and market caps from CoinGecko |
| `intel_stablecoin_status` | Stablecoin peg health (USDT, USDC, DAI, FDUSD) |
| `intel_etf_flows` | Bitcoin spot ETF prices and volumes |
| `intel_sector_heatmap` | US equity sector performance (11 SPDR ETFs) |
| `intel_macro_signals` | 7 macro indicators (Fear & Greed, VIX, DXY, gold, 10Y, BTC) |
| `intel_commodity_quotes` | Commodity futures (gold, silver, crude, natgas, grains) |

### Forex & Currency (3)
| Tool | Description |
|------|-------------|
| `intel_forex_rates` | Latest FX rates from ECB. Filter by base/target currencies |
| `intel_forex_timeseries` | Historical FX rate with trend analysis (configurable days) |
| `intel_major_crosses` | All 8 major pairs + cross rates + DXY proxy |

### Bonds & Yields (2)
| Tool | Description |
|------|-------------|
| `intel_yield_curve` | US Treasury yield curve (2Y-30Y), 2s10s/3m10y spreads, inversion flag |
| `intel_bond_indices` | Bond ETFs: AGG, TLT, HYG, LQD, TIP with price/change |

### Earnings (2)
| Tool | Description |
|------|-------------|
| `intel_earnings_calendar` | Upcoming earnings for 20 mega-cap stocks with EPS estimates |
| `intel_earnings_surprise` | Historical earnings surprise (actual vs estimate, trend) |

### SEC Filings (3)
| Tool | Description |
|------|-------------|
| `intel_sec_filings` | Full-text search across all EDGAR filings |
| `intel_company_filings` | Company filings by ticker (10-K, 10-Q, 8-K) with CIK resolution |
| `intel_recent_8k` | Latest 8-K material events (M&A, exec changes, earnings) |

### Company Enrichment (1)
| Tool | Description |
|------|-------------|
| `intel_company_profile` | Composite profile: stock quote + financials + news + SEC + GitHub |

### Macro Composite (1)
| Tool | Description |
|------|-------------|
| `intel_macro_composite` | Weighted market score (0-100) with verdict: RISK_ON to STRONG_CAUTION |

### Economic (6)
| Tool | Description |
|------|-------------|
| `intel_gas_prices` | Daily US retail gasoline, diesel, and E85 prices from AAA |
| `intel_residential_natgas` | US residential natural gas prices from EIA |
| `intel_electricity_rates` | US electricity retail rates by sector/state from EIA |
| `intel_energy_prices` | Brent/WTI crude oil and natural gas from EIA |
| `intel_fred_series` | FRED economic data (GDP, CPI, unemployment, rates) |
| `intel_world_bank_indicators` | World Bank development indicators by country |

### Central Banks (1)
| Tool | Description |
|------|-------------|
| `intel_central_bank_rates` | Policy rates for 15 major central banks |

### BTC Technicals (1)
| Tool | Description |
|------|-------------|
| `intel_btc_technicals` | Bitcoin SMA 50/200, golden/death cross, Mayer Multiple |

### Natural Disasters (2)
| Tool | Description |
|------|-------------|
| `intel_earthquakes` | USGS earthquakes (configurable magnitude/time/limit) |
| `intel_wildfires` | NASA FIRMS satellite fire hotspots (9 global regions) |

### Environmental (2)
| Tool | Description |
|------|-------------|
| `intel_environmental_events` | NASA EONET natural events |
| `intel_disaster_alerts` | GDACS disaster alerts with severity scoring |

### Conflict & Security (4)
| Tool | Description |
|------|-------------|
| `intel_acled_events` | ACLED armed conflict events |
| `intel_ucdp_events` | Uppsala Conflict Data Program events |
| `intel_unrest_events` | Social unrest with Haversine dedup |
| `intel_humanitarian_summary` | HDX humanitarian crisis datasets |

### Military & Defense (6)
| Tool | Description |
|------|-------------|
| `intel_military_flights` | Military aircraft via adsb.lol (OpenSky fallback) |
| `intel_theater_posture` | Activity across 5 theaters (EU, Indo-Pacific, ME, Arctic, Korea) |
| `intel_aircraft_details` | Aircraft lookup by ICAO24 hex (hexdb.io) |
| `intel_aircraft_batch` | Batch aircraft lookup (multiple hex codes) |
| `intel_military_surge` | Foreign aircraft concentration anomaly detection |
| `intel_usni_fleet` | USNI News naval fleet tracker |

### Infrastructure (4)
| Tool | Description |
|------|-------------|
| `intel_internet_outages` | Cloudflare Radar internet disruptions |
| `intel_cable_health` | Submarine cable corridor health |
| `intel_cascade_analysis` | Infrastructure cascade simulation |
| `intel_service_status` | Cloud platform health (AWS, Azure, GCP, Cloudflare, GitHub) |

### Maritime (2)
| Tool | Description |
|------|-------------|
| `intel_nav_warnings` | NGA maritime navigation warnings |
| `intel_vessel_snapshot` | Naval activity at 9 strategic waterways |

### Geospatial Datasets (10)
| Tool | Description |
|------|-------------|
| `intel_military_bases` | 70 military bases from 9 operators |
| `intel_strategic_ports` | 40 strategic ports across 6 types |
| `intel_pipelines` | 24 oil/gas/hydrogen pipelines |
| `intel_nuclear_facilities` | 24 nuclear power/enrichment/research facilities |
| `intel_undersea_cables` | 34 submarine communications cables |
| `intel_ai_datacenters` | 48 AI/HPC datacenters worldwide |
| `intel_spaceports` | 27 global spaceports |
| `intel_critical_minerals` | 27 strategic mineral deposits |
| `intel_stock_exchanges` | 82 stock exchanges worldwide |
| `intel_trade_routes` | Major trade routes and chokepoints |

### News & Media (3)
| Tool | Description |
|------|-------------|
| `intel_news_feed` | 119 global RSS feeds with 4-tier source ranking |
| `intel_trending_keywords` | Trending terms with spike detection |
| `intel_gdelt_search` | GDELT 2.0 global news search |

### Intelligence Analysis (8)
| Tool | Description |
|------|-------------|
| `intel_signal_convergence` | Geographic convergence of multi-domain signals |
| `intel_focal_points` | Multi-signal focal point detection |
| `intel_signal_summary` | Country-level signal aggregation |
| `intel_temporal_anomalies` | Activity deviations from baselines |
| `intel_instability_index` | Country Instability Index v2 (0-100) |
| `intel_risk_scores` | ACLED-based conflict risk scoring |
| `intel_hotspot_escalation` | Escalation scores for 22 intel hotspots |
| `intel_country_dossier` | Comprehensive country intelligence dossier |

### NLP Intelligence (4)
| Tool | Description |
|------|-------------|
| `intel_extract_entities` | Named entity extraction (countries, leaders, orgs, CVEs, APTs) |
| `intel_classify_event` | Event classification into 14 threat categories |
| `intel_news_clusters` | Topic clustering by Jaccard similarity |
| `intel_keyword_spikes` | Keyword spike detection with Welford's algorithm |

### Strategic Synthesis (4)
| Tool | Description |
|------|-------------|
| `intel_strategic_posture` | Composite global risk from 9 weighted domains |
| `intel_world_brief` | Structured daily intelligence summary |
| `intel_fleet_report` | Naval fleet activity report with readiness scoring |
| `intel_population_exposure` | Population at risk near active events (105-city dataset) |

### Climate (1)
| Tool | Description |
|------|-------------|
| `intel_climate_anomalies` | Open-Meteo temperature/precipitation anomalies |

### Prediction Markets (1)
| Tool | Description |
|------|-------------|
| `intel_prediction_markets` | Polymarket prediction contracts |

### Elections (1)
| Tool | Description |
|------|-------------|
| `intel_election_calendar` | Global election calendar with risk scoring |

### Displacement (1)
| Tool | Description |
|------|-------------|
| `intel_displacement_summary` | UNHCR refugee/IDP statistics |

### Aviation (2)
| Tool | Description |
|------|-------------|
| `intel_airport_delays` | FAA airport delay status |
| `intel_aviation_domestic` | Global air traffic snapshot from OpenSky |

### Cyber Threats (1)
| Tool | Description |
|------|-------------|
| `intel_cyber_threats` | Aggregated cyber intel (URLhaus, CISA KEV, SANS) |

### Space Weather (1)
| Tool | Description |
|------|-------------|
| `intel_space_weather` | Solar activity (Kp index, X-ray flux, SWPC alerts) |

### AI & Technology (4)
| Tool | Description |
|------|-------------|
| `intel_ai_releases` | arXiv AI papers, HuggingFace models |
| `intel_hacker_news` | Hacker News top stories |
| `intel_trending_repos` | GitHub trending repositories |
| `intel_arxiv_papers` | arXiv paper search |

### Health (1)
| Tool | Description |
|------|-------------|
| `intel_disease_outbreaks` | WHO DON, ProMED, CIDRAP outbreaks |

### Social & Sanctions (3)
| Tool | Description |
|------|-------------|
| `intel_social_signals` | Reddit geopolitical discussion velocity |
| `intel_sanctions_search` | OFAC SDN list search |
| `intel_nuclear_monitor` | Seismic monitoring near nuclear test sites |

### Shipping & Trade (1)
| Tool | Description |
|------|-------------|
| `intel_shipping_index` | Dry bulk shipping stress index |

### Government (1)
| Tool | Description |
|------|-------------|
| `intel_usa_spending` | USAspending.gov federal contracts |

### Country Intelligence (3)
| Tool | Description |
|------|-------------|
| `intel_country_brief` | Quick country situation summary |
| `intel_country_stocks` | Stock exchanges and listings by country |
| `intel_financial_centers` | Global financial centers ranking |

### Extended Geospatial (1)
| Tool | Description |
|------|-------------|
| `intel_cloud_regions` | Cloud provider regions worldwide |

### Traffic (2)
| Tool | Description |
|------|-------------|
| `intel_traffic_flow` | Road traffic flow data |
| `intel_traffic_incidents` | Real-time traffic incidents |

### Cross-Domain Alerts (2)
| Tool | Description |
|------|-------------|
| `intel_alert_digest` | Cross-domain alert aggregation |
| `intel_weekly_trends` | Weekly trend analysis |

### Monitoring (2)
| Tool | Description |
|------|-------------|
| `intel_webcams` | Public webcam locations and live previews |
| `intel_status` | Server health, cache stats, circuit breaker status |

### Vector Search (5)
| Tool | Description |
|------|-------------|
| `intel_semantic_search` | Natural language search across all accumulated intelligence |
| `intel_similar_events` | Find events similar to a given data point |
| `intel_timeline` | Chronological view of intelligence for a domain/category |
| `intel_vector_stats` | Vector store collection statistics |
| `intel_collect` | Trigger an on-demand collection cycle |

### Cross-Domain Analytics (3)
| Tool | Description |
|------|-------------|
| `intel_cross_correlate` | Find correlated signals across all domains for a given topic |
| `intel_domain_summary` | Per-category summary of stored intelligence (counts, sources, recency) |
| `intel_trend_detection` | Detect activity surges/drops by comparing recent vs baseline periods |

### Reports (1)

| Tool | Description |
|------|-------------|
| `intel_generate_report` | Generate a PDF or HTML intelligence report covering 18 domains in parallel |

### AOI Geofences (5)
| Tool | Description |
|------|-------------|
| `intel_aoi_define` | Define a named area of interest: point + radius in km (1-2000) |
| `intel_aoi_list` | List all user-defined AOIs |
| `intel_aoi_delete` | Delete a user-defined AOI by name |
| `intel_aoi_brief` | Cited brief for an AOI: earthquakes, military flights, wildfires, conflict events, aviation, nearby infrastructure, and news mentions, all filtered to the AOI's radius |
| `intel_aoi_escalation` | Hotspot escalation scoring (same engine as the 22 built-in hotspots) applied to a user AOI |

### Situation Brief (1)
| Tool | Description |
|------|-------------|
| `intel_situation_brief` | Cited situational awareness brief, generated on demand over MCP: a bounded server-side overview (earthquakes, military flights, ACLED conflict events, wildfires, cyber threats, disease outbreaks, news, space weather, strategic posture, alert digest), synthesized via local Ollama or a mechanically-cited fallback when Ollama is unreachable |

---

## Watching your own area (geofences/AOIs)

Static infrastructure results (bases, ports, nuclear, cables, datacenters, spaceports) draw on this repo's curated strategic datasets, which are global and deliberately sparse, not exhaustive local registries. A quiet AOI brief means nothing from those curated sets is in range, not that your area has no infrastructure.

Before the AOI family, only `intel_signal_convergence` accepted a real
point-plus-radius, `intel_military_flights` took a bbox, and hotspot
escalation scoring was restricted to the 22 hardcoded `INTEL_HOTSPOTS`.
The `intel_aoi_*` tools let you name your own area (a city, a border
region, a facility) and get the same cited, multi-domain treatment.
Geofences survive the antimeridian (a Bering Strait or Fiji AOI queries
both sides of the dateline), and pipelines/undersea cables are matched
as line features via great-circle segment distance, not just by their
endpoints.

Define an AOI once, then brief, score, edit, and watch it. Three
shapes: a circle (point + radius), a polygon (3-64 vertices, for a
border region or strait a radius cannot express), or a corridor (a
waypoint route + width, for a shipping lane or supply road):

```
intel_aoi_define(name="Pittsburgh", lat=40.4406, lon=-79.9959, radius_km=50)
intel_aoi_define_polygon(name="Taiwan Strait", vertices=[[22.5, 118.0], [22.5, 121.5], [26.5, 122.0], [26.5, 118.5]])
intel_aoi_define_corridor(name="Suez Approach", waypoints=[[29.9, 32.55], [27.5, 34.0], [24.0, 36.0]], width_km=80)
intel_aoi_brief(name="Taiwan Strait")
intel_aoi_escalation(name="Pittsburgh")
intel_aoi_update(name="Pittsburgh", radius_km=100)   # resize/rename in place
intel_aoi_changes(name="Suez Approach")  # what entered/left since last sweep
intel_aoi_digest()  # one-call sweep across ALL your areas
```

The same nine operations are available from the terminal: `intel aoi define|define-polygon|define-corridor|list|update|delete|brief|escalation|changes`.

Membership is exact for the shape (an event inside a polygon's
bounding circle but outside the polygon is excluded); corridor
distances are measured to the route. Line-feature infrastructure
(pipelines, undersea cables) matches the bounding circle for
non-circle shapes, disclosed in `data_gaps`.

`intel_aoi_changes` is the alerting primitive: the first call records a
baseline, and every later call reports what entered and left the fence
per domain, with failed fetches reported as `data_gaps` rather than
counted as departures.

`intel_aoi_brief` filters every geo-capable domain to the 50 km radius
around Pittsburgh: earthquakes, military flights (bbox derived from the
radius), wildfires (region-mapped, since NASA FIRMS has no point+radius
query), ACLED conflict events, a sample of nearby aviation traffic,
nearby static infrastructure (military bases, ports, pipelines, nuclear
facilities, undersea cables, datacenters, spaceports) with distances in
km, and news headline mentions of "Pittsburgh". Every item in the
response carries a `[n]` citation into a numbered `sources` list, and
`data_gaps` names any domain that couldn't be scoped to the AOI (for
example, wildfires when the AOI falls outside NASA FIRMS's coverage
regions, or conflict events when ACLED credentials aren't configured)
instead of silently omitting it.

`intel_aoi_escalation` runs the same baseline/military/conflict/social-
unrest scoring engine that powers `intel_hotspot_escalation` for the 22
built-in hotspots, but scoped to your AOI's own radius instead of a fixed
2-degree window.

AOIs persist in a dedicated table inside the same SQLite cache database
the server already uses (`~/.cache/world-intel-mcp/cache.db` by default,
or `$WORLD_INTEL_CACHE_DB`), so a scheduled agent can watch any named
area across restarts with `intel_aoi_list` / `intel_aoi_delete` to manage
them.

---

## Vector Store

The optional Qdrant vector store accumulates intelligence over time for semantic retrieval. All data fetched through the Fetcher is automatically embedded and stored.

### Setup

```bash
# Install Qdrant (Docker)
docker run -p 6333:6333 qdrant/qdrant

# Install vector dependencies
pip install -e ".[vector]"

# Run the collector daemon (populates vector store 24/7)
intel-collector --daemon              # every 5 minutes
intel-collector --daemon --interval 120  # every 2 minutes
intel-collector --sources markets,cyber  # specific domains only
intel-collector                        # single collection cycle
intel-collector --daemon --sources aoi --interval 900  # AOI watch only: sweep every geofence every 15 min
```

The `aoi` group runs `intel_aoi_digest` as a sweep: each cycle diffs every
defined AOI against its stored snapshot and advances it, so the daemon
interval is your geofence watch cadence. Change digests are logged and
(when the vector store is enabled) stored for semantic search. Set
`WORLD_INTEL_AOI_WEBHOOK` to get a POST whenever a sweep finds something
entered or left a geofence (quiet sweeps never fire); with
`WORLD_INTEL_AOI_WEBHOOK_FORMAT=text` the body is raw markdown with a
`Title` header, which ntfy-style sinks render directly.

### Running as a macOS launchd Service

`scripts/collector-daemon.sh` manages the collector as a `launchd` agent so it
survives reboots. It fills in `com.agentic.intel-collector.plist.template`
with this checkout's own path (resolved from the script's own location, so
it works from any clone) and installs the result to
`~/Library/LaunchAgents/`.

```bash
scripts/collector-daemon.sh start    # install + load the launchd job
scripts/collector-daemon.sh status   # check state and log info
scripts/collector-daemon.sh logs     # tail stdout (logs err for stderr)
scripts/collector-daemon.sh stop     # unload the launchd job
scripts/collector-daemon.sh restart
scripts/collector-daemon.sh render   # print the filled-in plist without installing it
```

### Semantic Search Examples

Once data accumulates, AI agents can query across all domains:

- *"military activity near Taiwan strait"* — finds military flights, naval warnings, theater posture data
- *"cyber threats targeting healthcare"* — finds URLhaus, CISA KEV entries related to healthcare
- *"economic indicators suggesting recession"* — finds yield curve inversions, macro signals, FRED data

The vector store uses FastEmbed (ONNX-based, BAAI/bge-small-en-v1.5) for embeddings — no GPU required, ~3 second cold start.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ACLED_ACCESS_TOKEN` | No | ACLED conflict events |
| `NASA_FIRMS_API_KEY` | No | Satellite wildfire data |
| `EIA_API_KEY` | No | Energy price data |
| `CLOUDFLARE_API_TOKEN` | No | Internet outage data |
| `FRED_API_KEY` | No | Macro economic data (also used for yield curve) |
| `OPENSKY_CLIENT_ID` | No | Military flight fallback |
| `OPENSKY_CLIENT_SECRET` | No | Military flight fallback |
| `OLLAMA_API_URL` | No | Ollama server for AI-generated briefs (default: `http://localhost:11434`) |
| `OLLAMA_MODEL` | No | Ollama model for AI-generated briefs (default: `llama3.2`) |
| `WORLD_INTEL_LOG_LEVEL` | No | Logging level (default: INFO) |
| `WORLD_INTEL_AOI_WEBHOOK` | No | URL POSTed when an AOI sweep finds changes (collector daemon); quiet sweeps don't fire |
| `WORLD_INTEL_AOI_WEBHOOK_FORMAT` | No | `json` (default: title/totals/markdown payload) or `text` (raw markdown body + `Title` header, ntfy-style) |

Everything else uses free, unauthenticated public APIs.

---

## Development

```bash
pip install -e ".[dev]"
pytest                       # 900 tests (918 total, 18 live-network smoke tests deselected by default)
pytest --cov=world_intel_mcp # with coverage
pytest tests/test_forex.py -v # single module
```

### Adding a New Source

1. Create `sources/your_source.py` with `async def fetch_your_data(fetcher: Fetcher, **kwargs) -> dict`
2. Use `fetcher.get_json(url, source="your-source", cache_key=..., cache_ttl=300)` — automatic caching, retries, circuit breaking, rate limiting
3. In `server.py`: add `Tool(...)` to `TOOLS`, add `case` to `_dispatch()` (use inline import)
4. Add tests using `respx` to mock HTTP (see `tests/test_forex.py` for pattern)
5. Optionally add to `dashboard/app.py` (SSE) and `cli.py` (Click)

---

## License

MIT
