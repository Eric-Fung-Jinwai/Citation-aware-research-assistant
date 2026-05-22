
# Stock Analysis System — Implementation TODO

---

## Phase 0: Project Setup

**Goal:** Establish the project skeleton, dependencies, and config before writing any logic.

### Tasks
- [ ] Create the full directory structure (see layout below)
- [ ] Create `requirements.txt` with all dependencies
- [ ] Create `.env.example` listing required API keys
- [ ] Create `.env` locally (gitignored) and fill in real keys
- [ ] Verify API keys work: Polygon.io (or yfinance), NewsAPI, Anthropic/OpenAI

### Files to Create
```
Stock-Analysis-System/
├── backend/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entry point
│   ├── skills/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── utils/
│   │   └── __init__.py
│   └── prompts/
│       └── __init__.py
├── frontend/
│   └── app.py                    # Streamlit UI (placeholder for now)
├── requirements.txt
├── .env.example
└── .gitignore
```

---

## Phase 1: Atomic Skills — Data Layer

**Goal:** Independently fetchable data skills, each returning a structured result envelope.

### 1A — `market-data` skill
- [x] Fetch OHLCV, volume, returns, and volatility for a given ticker + window
- [x] Compute simple moving averages (20d, 50d, 200d)
- [x] Return result envelope: `{ status, data, error, source }`
- [x] Attach a `CitationObject` to every output block

**Files to Create**
```
backend/skills/market_data.py
backend/models/citation.py        # CitationObject schema (Pydantic)
```

### 1B — `web-access` skill
- [x] Fetch recent news articles for a ticker via NewsAPI (or SerpAPI/Benzinga)
- [x] Return list of `{ title, summary, source, url, date }`
- [x] Attach a `CitationObject` per article
- [x] Handle timeout / rate-limit gracefully → return degraded envelope

**Files to Create**
```
backend/skills/web_access.py
```

### 1C — `tech-indicator` skill
- [x] Compute: MA/EMA, RSI(14), MACD, Bollinger Bands, ATR, OBV
- [x] Accept OHLCV data from `market-data` (do not re-fetch)
- [x] Return indicators as structured dict + `CitationObject` (source: Polygon.io/yfinance)
- [x] Handle computation errors → degraded envelope

**Files to Create**
```
backend/skills/tech_indicator.py
```

---

## Phase 2: Synthesis Layer — stock-retro + Citations

**Goal:** Assemble the context bundle and run LLM synthesis with full citation tagging.

### 2A — Citation system (core models + parser)
- [x] Define `CitationObject` Pydantic model (index, claim, source_type, source_name, url, date, excerpt)
- [x] Define `EvidenceBlock` model (citation_index, source_type, content, citation)
- [x] Define `ContextBundle` model (ticker, window, generated_at, evidence list)
- [x] Write `parse_citations(text, citation_map)` utility — regex replace `[cite:N]` → display markers

**Files to Create**
```
backend/models/citation.py        # (extend from Phase 1)
backend/models/report.py          # ReportOutput, ContextBundle, EvidenceBlock schemas
backend/utils/citation_parser.py  # parse_citations() function
```

### 2B — `stock-retro` composite skill
- [x] Call `market-data`, `web-access`, and `tech-indicator` concurrently (asyncio)
- [x] Assemble `ContextBundle`: assign sequential `citation_index` values per report
- [x] Fill degraded placeholders for any failed skill
- [x] Pass bundle to LLM synthesis step

**Files to Create**
```
backend/skills/stock_retro.py
```

### 2C — LLM synthesis prompts
- [x] Write system prompt including full citation rules (Section 8.4 verbatim block)
- [x] Write report structure prompt (8 sections: Price Action → Confidence Assessment)
- [x] Wire up to Claude/GPT-4o API call, passing the `ContextBundle` as user message
- [x] Verify LLM output contains `[cite:N]` tags (integration test)

**Files to Create**
```
backend/prompts/synthesis.py      # system prompt + report structure template
backend/prompts/citation_rules.py # citation rules block (imported into synthesis.py)
```

---

## Phase 3: Quality Gates

**Goal:** Add confidence filtering and thesis backtesting.

### 3A — `confidence-gate`
- [x] Parse confidence score from LLM output (or ask LLM to return it explicitly)
- [x] Map score to tier: High (≥60%) / Moderate (45–60%) / Low (33–45%) / Very Low (<33%)
- [x] Block report output if confidence < 33% and return a structured refusal message
- [x] Pass report + citations through if threshold met

**Files to Create**
```
backend/skills/confidence_gate.py
```

### working 3B — `view-validator`
- [x] Accept free-text thesis + ticker + timeframe as input
- [x] Extract direction (bullish/bearish) from thesis via LLM
- [x] Pull historical price data for the specified timeframe
- [x] Compute: total return, max drawdown, Sharpe ratio, benchmark comparison (SPY)
- [x] Return verdict: directionally correct/incorrect + metrics table

**Files to Create**
```
backend/skills/view_validator.py
```

---

## Phase 4: RAG Layer — SEC Filings

**Goal:** Add semantic search over 10-K, 10-Q, 8-K filings.

### Tasks
- [x] Set up ChromaDB (local persistent store)
- [x] Write SEC EDGAR fetcher: download recent filings for a ticker via EDGAR full-text search API
- [x] Chunk filings into 500–800 token blocks with metadata (ticker, form type, date, url)
- [x] Embed and upsert chunks into ChromaDB
- [x] Write `finance-rag` skill: semantic query → top-k results → `EvidenceBlock[]` with citations
- [x] Handle DB errors / no results → degraded envelope

**Files to Create**
```
backend/skills/finance_rag.py
backend/utils/sec_fetcher.py      # EDGAR download + chunking
backend/utils/vector_store.py     # ChromaDB init, upsert, query wrappers
data/                             # ChromaDB persistent storage (gitignored)
```

---

## Phase 5: Frontend — Streamlit UI

**Goal:** End-to-end demo-ready UI with inline citation rendering.

### Tasks
- [x] Input form: ticker symbol, analysis window (7d / 30d / 90d), optional thesis for view-validator
- [x] Call backend FastAPI endpoint and display loading state
- [x] Render structured report sections (Price Action → Confidence Assessment)
- [x] Implement `render_report_with_citations()` using `parse_citations()` (Section 8.6 code)
- [x] Render footnotes: clickable `[↗]` for URL citations, plain text for data sources
- [x] Display confidence tier badge (color-coded: green / yellow / orange / red)
- [x] Add view-validator panel (optional thesis input → verdict + metrics)
- [x] Handle degraded sections gracefully (show "Unavailable" notice per section)

**Files to Create / Update**
```
frontend/app.py                   # Main Streamlit app
frontend/components/
    ├── report_view.py            # Report rendering + citation footnotes
    ├── confidence_badge.py       # Confidence tier display
    └── validator_panel.py        # View-validator input + verdict display
```

---

## Phase 6: API Layer — FastAPI Wiring

**Goal:** Expose skills as HTTP endpoints so the frontend and future clients can call them.

### Tasks
- [x] `POST /analyze` → runs full stock-retro pipeline, returns report + citations
- [x] `POST /validate-view` → runs view-validator, returns verdict + metrics
- [x] `GET /health` → returns service status
- [x] Add request/response Pydantic models for all endpoints
- [x] Add basic error handling middleware

**Files to Create / Update**
```
backend/main.py                   # FastAPI app + route registration
backend/routers/
    ├── analyze.py                # /analyze endpoint
    └── validate.py               # /validate-view endpoint
```

---

## Phase 7 (Later): Advanced Enhancements

These are explicitly out of scope for MVP. Do not start until Phases 1–6 are stable.

- [ ] `macro-context` skill (FRED API — Fed funds rate, Treasury yields, CPI)
- [ ] `options-flow` skill (unusual options activity)
- [ ] ML signal layer (XGBoost/LightGBM on returns + RSI + MACD + volume)
- [ ] Migrate frontend to Next.js + keep FastAPI backend
- [ ] Split deployment: frontend / backend / vector DB on separate services

---

## API Keys Needed (`.env`)

| Key | Service            | Used By                  |
|---|--------------------|--------------------------|
| `ANTHROPIC_API_KEY` | Anthropic (optional) | Alt <br/>LLM synthesis        |
| `NEWSAPI_KEY` | NewsAPI.org        | web-access               |
| `POLYGON_API_KEY` | Polygon.io         | market-data (production) |
| `OPENAI_API_KEY` | OpenAI     | LLM synthesis            |

---

## Dependency List (`requirements.txt` — preliminary)

```
fastapi
uvicorn
pydantic
python-dotenv
yfinance
pandas
pandas-ta
requests
anthropic
openai
chromadb
langchain
langchain-anthropic
sentence-transformers
streamlit
pytest
pytest-asyncio
httpx
```