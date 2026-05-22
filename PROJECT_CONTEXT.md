# Stock Analysis System — Project Context

> Read this file first at the start of every session.
> It summarises what has been built, decisions made, and what comes next.

---

## What This Project Is

A citation-aware US equity research assistant that synthesizes market data,
technical indicators, and financial news into structured research reports.

It is NOT a trading bot or prediction engine.
Full spec: `revised_us_stock_analysis_agent.md`
Full TODO: `TODO.md`

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| LLM | OpenAI GPT-4o | Function calling + synthesis |
| Market data | Polygon.io (free tier) | End-of-day data, delayed |
| News | NewsAPI (free tier) | 100 req/day, enough for dev |
| Indicators | pandas-ta | RSI, MACD, BB, ATR, OBV, EMA |
| Trading calendar | pandas-market-calendars | NYSE holiday-aware date snapping |
| Vector DB | ChromaDB (local) | SEC filing RAG |
| Orchestration | LangGraph | Agent routing |
| Backend | FastAPI | API layer |
| Frontend | Streamlit (Phase 1) → Next.js (later) | |

API keys are in `.env` (gitignored). Template is `.env.example`.

---

## Directory Structure (current state)

```
Stock-Analysis-System/
├── backend/
│   ├── main.py                        ✅ FastAPI app (health endpoint only)
│   ├── skills/
│   │   ├── market_data.py             ✅ Polygon.io OHLCV + MA20/50/200
│   │   ├── tech_indicator.py          ✅ RSI, MACD, BB, ATR, OBV, EMA (pandas-ta)
│   │   └── web_access.py             ✅ NewsAPI top-5 articles
│   ├── models/
│   │   └── citation.py               ✅ CitationObject + SkillResult (Pydantic)
│   ├── utils/
│   │   └── dates.py                  ✅ NYSE-aware last_trading_day()
│   ├── prompts/                       ⬜ empty — Phase 2
│   └── routers/                      ⬜ empty — Phase 6
├── frontend/
│   └── app.py                        ⬜ Streamlit placeholder
├── data/                             ⬜ ChromaDB storage (Phase 4)
├── requirements.txt                  ✅
├── .env                              ✅ (gitignored, keys filled in)
├── .env.example                      ✅ (placeholder values only)
├── .gitignore                        ✅
├── TODO.md                           ✅ Full phased plan
└── revised_us_stock_analysis_agent.md ✅ Original spec
```

---

## What Has Been Built (Phases 0 and 1 complete)

### Phase 0 — Project Setup ✅
- Full directory structure
- `requirements.txt`
- `.env` / `.env.example`
- `.gitignore`
- FastAPI health endpoint

### Phase 1 — Atomic Skills ✅

**`backend/models/citation.py`**
- `CitationObject` — carries source metadata for every fetched data point
- `SkillResult` — standard envelope: `{ status, data, citations, error, source }`

**`backend/skills/market_data.py`**
- `fetch_market_data(ticker, window, as_of)` async function
- Fetches 210 days from Polygon.io so MA200 can always be computed
- Trims to requested window (7d / 30d / 90d)
- Returns OHLCV, MA20/50/200, return%, annualised volatility, avg volume
- Passes `full_history` key so tech_indicator has enough data for long-period indicators
- `market-data` failure = hard abort (no price data = no report, per spec)

**`backend/skills/tech_indicator.py`**
- `compute_indicators(ticker, ohlcv_records)` async function
- Accepts `full_history` from market_data output (not re-fetching)
- Computes: RSI(14), MACD(12/26/9), BBands(20), ATR(14), OBV, EMA20, EMA50
- Degrades gracefully on failure

**`backend/skills/web_access.py`**
- `fetch_news(ticker, company_name, days)` async function
- Fetches top 5 articles from NewsAPI
- Each article gets its own CitationObject
- Degrades gracefully on timeout / rate limit

**`backend/utils/dates.py`**
- `last_trading_day(date, lookback_days)` 
- Uses NYSE calendar (pandas-market-calendars) — handles weekends + all US holidays
- Adapted from `get_last_open_date()` pattern in the A-share reference project
- 14-day lookback buffer covers long holiday stretches (Christmas/New Year)

---

## Key Design Decisions

- All skills return a `SkillResult` envelope — consistent interface for stock-retro
- `citation_index` is NOT assigned by atomic skills — stock-retro assigns it when assembling the bundle
- `market_data` always fetches 210 days regardless of window — supports MA200 and tech indicators
- Trading day resolution uses NYSE calendar, not just weekday check — handles July 4, Thanksgiving, etc.
- No LoRA / Qwen in this project — that was a separate context
- Advanced ML (LSTM, GRU, ensemble) is Phase 7 — do not build early

---

## Ensemble ML Note (teacher's concept — for Phase 7)

Teacher mentioned weighted ensemble of LSTM + GRU (e.g. 0.75 / 0.25):
- Each model predicts independently
- Final = w1 × LSTM_pred + w2 × GRU_pred (weights sum to 1.0)
- Weights chosen by backtesting or optimisation (not learned dynamically unless using stacking)
- Reduces variance — diverse models cancel out each other's mistakes
- Reference: `05_hybrid_prediction.py` in the course material does exactly this

---

## Reference Material

Course material at:
`/Users/ericfung/Desktop/zhima/Week14课件/智能体Stock/`

Key files:
- `01_data_fetch.py` — A-share data fetch with trading calendar backtrack (Tushare)
- `02_analysis.py` — Azure OpenAI 8-dimension market analysis report
- `03_stock_prediction.py` — sector heatmap + individual stock scoring
- `05_hybrid_prediction.py` — LSTM + GRU hybrid ensemble (Phase 7 reference)

Their stack: Tushare + Azure OpenAI (A-shares). Ours: Polygon.io + OpenAI (US stocks).

---

## What Comes Next

### Phase 2 — Synthesis Layer
1. `backend/models/report.py` — EvidenceBlock, ContextBundle schemas
2. `backend/utils/citation_parser.py` — parse `[cite:N]` tags → footnotes
3. `backend/skills/stock_retro.py` — calls all 3 skills concurrently, assembles ContextBundle
4. `backend/prompts/synthesis.py` — system prompt with citation rules (Section 8.4 of spec)
5. Wire LLM call → structured 8-section report with `[cite:N]` inline tags

### Phase 3 — Quality Gates
- `confidence_gate.py`
- `view_validator.py`

### Phase 4 — RAG
- ChromaDB + SEC EDGAR fetcher + `finance_rag.py`

### Phase 5 — Streamlit UI
- Citation rendering, confidence badge, view-validator panel

### Phase 6 — FastAPI Routing
- `/analyze` and `/validate-view` endpoints

### Phase 7 — Advanced (do not start early)
- macro-context, options-flow, LSTM+GRU ensemble

---

## How to Run (current state)

```bash
cd /Volumes/MyNVMe/123/Stock-Analysis-System

# Install dependencies
pip install -r requirements.txt

# Start API
uvicorn backend.main:app --reload

# Start frontend
streamlit run frontend/app.py
```