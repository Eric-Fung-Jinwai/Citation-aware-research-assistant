# Revised US Stock Analysis Agent — Product-Focused Architecture

> Adapted from the original guideline with emphasis on:
> - Portfolio/demo readiness
> - Research-oriented positioning instead of direct trading advice
> - Faster implementation path
> - Better credibility and explainability
> - Reduced unnecessary ML complexity in early phases

# 1. Product Positioning

## Core Product Identity

This system should be framed as:

> **An evidence-based US equity research assistant that synthesizes market data, SEC filings, technical indicators, and financial news into structured stock analysis reports with source citations and confidence gating.**

The system is **NOT**:
- a high-frequency trading engine
- an autonomous trading bot
- a guaranteed prediction system
- a direct financial advisor

# 2. Core Philosophy

## Primary Principle

The LLM should:
- synthesize
- explain
- compare evidence
- summarize uncertainty

The LLM should NOT:
- hallucinate unsupported claims
- output uncited financial statements
- pretend to predict markets with certainty

# 3. Recommended MVP Scope

The original architecture is strong but too broad for an initial portfolio-quality implementation.

## Recommended MVP

Build only these first:

| Component | Priority |
|---|---|
| market-data | Critical |
| web-access | Critical |
| tech-indicator | Critical |
| stock-retro | Critical |
| citation system | Critical |
| confidence gate | High |
| view-validator | High |
| finance-rag | Medium |

Do NOT begin with:
- LSTM ensembles
- reinforcement learning
- options-flow
- real-time streaming
- portfolio optimization
- multi-agent chains

Those are later-stage enhancements.

# 4. Revised System Architecture

```text
User
  ↓
Frontend UI
  ↓
LLM Agent Router
  ↓
Atomic Skills
  ├── market-data
  ├── web-access
  ├── tech-indicator
  └── finance-rag
  ↓
Synthesis Layer
  ↓
Confidence Gate
  ↓
Structured Research Report
```

# 5. Frontend Recommendations

## Best Choice for Portfolio

### Phase 1
Use:
- Streamlit

Why:
- fastest development
- simple deployment
- ideal for demos/interviews

### Phase 2
Upgrade to:
- Next.js + FastAPI

Only after:
- the backend pipeline is stable

# 6. Revised Report Structure

Instead of:

❌ Buy / Sell recommendations

Use:

## Structured Evidence Report

### 1. Price Action Summary
What happened recently?

### 2. Fundamental Drivers
What news/events likely caused it?

### 3. Technical Signals
What indicators support or contradict momentum?

### 4. SEC Filing Highlights
Any important statements from recent filings?

### 5. Bullish Evidence
List supporting signals.

### 6. Bearish Evidence
List contradicting signals.

### 7. Uncertainty & Risk Factors
Explain uncertainty explicitly.

### 8. Confidence Assessment
Example:
- High confidence
- Moderate confidence
- Weak signal / monitor only

# 7. Confidence Framework (Revised)

## Recommended Output Categories

| Confidence | Output Style |
|---|---|
| High: confidence ≥ 60% | Strong evidence alignment |
| Moderate: confidence 45–60% | Mixed signals |
| Low: confidence 33–45% | Monitoring recommended |
| Very Low: confidence < 33% | Insufficient evidence |

Avoid:
- “Guaranteed upside”
- “Strong buy”
- “Certain reversal”

# Section 8 — Citation System Design

Every factual claim in the final report must be traceable to a source.
Citations are attached at the moment data is fetched and preserved through
every layer until they render as clickable references in the UI.

---

## 8.1 Citation Object Schema

Every piece of fetched data carries this envelope:

```python
{
  "index":       0,                    # auto-incremented per report
  "claim":       "NVDA revenue grew 122% YoY in Q4 2024",
  "source_type": "sec_filing",         # sec_filing | news | price_data | macro | technical
  "source_name": "NVIDIA 10-K 2024",
  "url":         "https://www.sec.gov/Archives/...",
  "date":        "2024-02-21",
  "excerpt":     "Total revenue of $22.1 billion for the quarter ended January 2024."
}
```

### Field Rules

| Field | Required | Notes |
|---|---|---|
| `index` | Yes | Assigned by `stock-retro` when assembling context bundle, not by atomic skill |
| `claim` | Yes | One sentence summarizing what this source supports |
| `source_type` | Yes | Must be one of: `sec_filing`, `news`, `price_data`, `macro`, `technical` |
| `source_name` | Yes | Human-readable name, e.g. `"NVIDIA 10-K 2024"`, `"Reuters"`, `"Polygon.io"` |
| `url` | Conditional | Required for `sec_filing` and `news`. May be `null` for `price_data` and `technical` |
| `date` | Yes | ISO 8601 format: `YYYY-MM-DD` |
| `excerpt` | Yes | 1–2 sentences maximum. No full paragraphs. Direct quote or close paraphrase |

### Source Type Reference

| source_type | Example Source | URL Required |
|---|---|---|
| `sec_filing` | NVIDIA 10-K, 8-K, 10-Q | Yes — link to SEC EDGAR |
| `news` | Reuters, Benzinga, NewsAPI | Yes — link to article |
| `price_data` | Polygon.io, yfinance | No — name only |
| `macro` | FRED API, Fed Reserve | Yes where available |
| `technical` | Polygon.io, TA-Lib computed | No — name only |

---

## 8.2 Citation Flow (L4 → L1)

Citations are created at the data layer and must survive every transformation
until they reach the UI renderer. The flow is strictly top-down — no layer
invents, modifies, or drops citations.

```
L4  Data Sources
    ┌─────────────────────────────────────────────┐
    │  Polygon.io / yfinance / SEC EDGAR / NewsAPI │
    └─────────────────────┬───────────────────────┘
                          │  raw data + metadata
                          ▼
L3  Atomic Skills
    ┌─────────────────────────────────────────────┐
    │  market-data                                 │
    │  web-access                                  │
    │  finance-rag                                 │
    │  tech-indicator                              │
    └─────────────────────┬───────────────────────┘
                          │  structured output + CitationObject[]
                          ▼
L3  stock-retro (composite skill)
    ┌─────────────────────────────────────────────┐
    │  assembles context bundle:                   │
    │  { "evidence": [...], "citations": [...] }   │
    │  assigns citation_index to each block        │
    └─────────────────────┬───────────────────────┘
                          │  numbered context bundle
                          ▼
L2  LLM Synthesis
    ┌─────────────────────────────────────────────┐
    │  receives evidence with citation_index       │
    │  tags claims inline: [cite:0], [cite:1]      │
    │  does NOT invent unsupported claims          │
    └─────────────────────┬───────────────────────┘
                          │  report text with [cite:N] tags
                          ▼
L2  Confidence Gate
    ┌─────────────────────────────────────────────┐
    │  passes report + citation list if threshold  │
    │  met. Blocks output if confidence too low.   │
    └─────────────────────┬───────────────────────┘
                          │  gated report + CitationObject[]
                          ▼
L1  UI Renderer
    ┌─────────────────────────────────────────────┐
    │  parses [cite:N] tags via regex              │
    │  resolves index → CitationObject             │
    │  renders inline superscript footnotes        │
    │  links footnotes to citation.url             │
    └─────────────────────┬───────────────────────┘
                          │
                          ▼
    Final Report with clickable inline citations
```

> **Critical failure point:** The L2 synthesis step. If the LLM is not
> explicitly instructed to preserve `[cite:N]` tags in its output, it will
> silently drop them during summarization. See Section 8.4 for the required
> prompt instruction.

---

## 8.3 Context Bundle Structure

`stock-retro` passes this structured bundle to the LLM — never raw
unstructured text. The bundle separates evidence content from citation
metadata so the LLM reasons over content while citation metadata remains
intact for the UI.

```python
{
  "ticker": "NVDA",
  "window": "7d",
  "generated_at": "2026-05-07T14:32:00Z",
  "evidence": [
    {
      "citation_index": 0,
      "source_type": "news",
      "content": "NVIDIA announced a strategic partnership with a major cloud provider,\
 expected to accelerate data center GPU adoption through 2025.",
      "citation": {
        "source_name": "Reuters",
        "url": "https://reuters.com/technology/nvidia-partnership-2026-05-01",
        "date": "2026-05-01"
      }
    },
    {
      "citation_index": 1,
      "source_type": "sec_filing",
      "content": "Revenue increased 122% year-over-year to $22.1 billion,\
 driven primarily by Data Center segment growth.",
      "citation": {
        "source_name": "NVIDIA 10-K 2024",
        "url": "https://www.sec.gov/Archives/edgar/data/1045810/...",
        "date": "2024-02-21"
      }
    },
    {
      "citation_index": 2,
      "source_type": "technical",
      "content": "RSI(14) crossed above 70 on May 5th. MACD histogram expanding\
 positively. Price trading above 50-day and 200-day moving averages.",
      "citation": {
        "source_name": "Polygon.io",
        "url": null,
        "date": "2026-05-06"
      }
    },
    {
      "citation_index": 3,
      "source_type": "price_data",
      "content": "NVDA closed at $892.54 on May 6th 2026, up 8.3% over the trailing\
 7-day window. Average daily volume 42.1M vs 30-day average of 38.6M.",
      "citation": {
        "source_name": "Polygon.io",
        "url": null,
        "date": "2026-05-06"
      }
    },
    {
      "citation_index": 4,
      "source_type": "macro",
      "content": "Federal funds rate held steady at 4.25–4.50% following May FOMC\
 meeting. 10-year Treasury yield at 4.31%.",
      "citation": {
        "source_name": "FRED API — Federal Reserve",
        "url": "https://fred.stlouisfed.org/series/FEDFUNDS",
        "date": "2026-05-07"
      }
    }
  ]
}
```

### Bundle Assembly Rules

- `citation_index` values are assigned sequentially starting at `0` per report
- Indexes reset on every new query — they are report-scoped, not global
- If an atomic skill returns multiple results (e.g. 5 news articles), each
  article gets its own evidence block with its own `citation_index`
- The LLM receives the full bundle; it does not fetch or modify citations

---

## 8.4 LLM Synthesis Prompt Instruction

Add this block verbatim to the **system prompt** of every `stock-retro`
synthesis call. It must appear before the report structure instructions.

```
CITATION RULES — YOU MUST FOLLOW THESE WITHOUT EXCEPTION:

You will receive a context bundle containing numbered evidence blocks.
Each block has a citation_index.

1. TAG EVERY CLAIM: Every factual statement in your report must end with
   [cite:N] where N is the citation_index of the supporting evidence block.

2. NO UNSUPPORTED CLAIMS: Do not state any fact that does not have a
   supporting evidence block. If you cannot tag it, do not write it.

3. MISSING SECTIONS: If evidence for a report section is marked UNAVAILABLE,
   write exactly: "Insufficient data available for this section."
   Do not infer, estimate, or fill the gap from your own knowledge.

4. MULTIPLE SOURCES: If a claim is supported by more than one evidence block,
   tag all of them: [cite:0][cite:1]

5. DO NOT MODIFY TAGS: Write citation tags exactly as [cite:N].
   Do not paraphrase, abbreviate, or reformat them.

Example of correct output:
  "NVIDIA revenue grew 122% year-over-year in Q4 2024 [cite:1], supported
   by a new cloud partnership announced last week [cite:0]. RSI above 70
   suggests near-term overbought conditions [cite:2]."

Example of incorrect output (do not do this):
  "NVIDIA has been performing well due to AI demand."   ← no citation tag
  "Revenue grew strongly [cite:1,2]"                   ← wrong tag format
```

---

## 8.5 Degraded Citation Handling

When an atomic skill fails, its evidence slot is filled with a structured
degraded placeholder. The LLM is never given a silent gap to fill — it
always receives an explicit signal that data is missing.

```python
{
  "citation_index": 5,
  "source_type": "news",
  "content": "UNAVAILABLE — web-access timed out after 10s",
  "citation": None
}
```

### What the LLM Outputs for a Degraded Block

```
Recent news context was unavailable at the time of this report.
```

### What the LLM Must NOT Output for a Degraded Block

```
❌ "Recent news suggests continued bullish sentiment..."
❌ "No significant news events were reported this week."
```

The first invents information. The second makes a factual claim without
evidence. Both violate the citation rules in Section 8.4.

### Degraded Block Trigger Conditions

| Skill | Trigger | Degraded Message |
|---|---|---|
| `market-data` | API error / timeout | Report aborts entirely — price data is non-negotiable |
| `web-access` | Timeout / rate limit | `"UNAVAILABLE — web-access timed out"` |
| `finance-rag` | DB error / no results | `"UNAVAILABLE — no relevant filings retrieved"` |
| `tech-indicator` | Computation error | `"UNAVAILABLE — indicators could not be computed"` |
| `macro-context` | FRED API error | `"UNAVAILABLE — macro data fetch failed"` |

---

## 8.6 UI Rendering

The UI resolves `[cite:N]` tags from LLM output into inline superscript
footnotes with clickable links.

### Rendered Example

```
NVIDIA revenue grew 122% YoY in Q4 2024 ¹ supported by a new cloud
partnership announced last week ². RSI above 70 suggests near-term
overbought conditions ³.

─────────────────────────────────────────────────────────
¹  NVIDIA 10-K 2024 — SEC EDGAR — 2024-02-21          [↗]
²  Reuters — 2026-05-01                                [↗]
³  Polygon.io — 2026-05-06
```

### Implementation Notes

**Parsing:**
```python
import re

def parse_citations(text: str, citation_map: dict) -> tuple[str, list]:
    """
    Replace [cite:N] tags with superscript markers.
    Returns cleaned text and ordered footnote list.
    """
    footnotes = []
    seen = {}
    counter = 1

    def replacer(match):
        nonlocal counter
        n = int(match.group(1))
        if n not in seen:
            seen[n] = counter
            footnotes.append(citation_map[n])
            counter += 1
        return f"[{seen[n]}]"

    clean_text = re.sub(r'\[cite:(\d+)\]', replacer, text)
    return clean_text, footnotes
```

**Rendering rules:**
- If `citation.url` is not null → render as clickable `[↗]` link
- If `citation.url` is null (e.g. technical indicators) → render source name only, no link
- Footnote numbering in the UI is display-only and independent of `citation_index`
- Footnotes are scoped per report — numbers reset to 1 on each new query
- Duplicate citations within the same report collapse to a single footnote entry

### Streamlit Implementation (Prototype)

```python
def render_report_with_citations(report_text: str, citations: list[dict]):
    clean_text, footnotes = parse_citations(report_text, {
        c["citation_index"]: c["citation"] for c in citations
    })

    st.markdown(clean_text)
    st.divider()
    st.markdown("**Sources**")

    for i, fn in enumerate(footnotes, start=1):
        if fn and fn.get("url"):
            st.markdown(f"{i}. [{fn['source_name']}]({fn['url']}) — {fn['date']}")
        elif fn:
            st.markdown(f"{i}. {fn['source_name']} — {fn['date']}")
        else:
            st.markdown(f"{i}. Source unavailable")
```

---

## 8.7 Citation Validation Checklist

Before shipping the citation system, verify each of the following:

- [ ] Every atomic skill attaches a `CitationObject` to every output block
- [ ] `stock-retro` assigns sequential `citation_index` values before calling LLM
- [ ] LLM synthesis prompt includes the full citation rules from Section 8.4
- [ ] LLM output is verified to contain `[cite:N]` tags in integration tests
- [ ] Degraded blocks produce the correct `UNAVAILABLE` message in LLM output
- [ ] UI parser correctly resolves all `[cite:N]` tags to footnotes
- [ ] Null `url` citations render without broken links
- [ ] Citation indexes reset per report, not globally
- [ ] `market-data` failure triggers full report abort, not degradation
# 9. Revised Atomic Skills

## market-data

### Purpose
Fetch:
- OHLCV
- volume
- returns
- volatility
- moving averages

### Recommended Stack

Prototype:
```python
yfinance
```

Production:
```python
Polygon.io
```

## web-access

### Purpose
Retrieve:
- recent news
- earnings announcements
- SEC filings
- press releases

### Output
```python
[
  {
    "title": "...",
    "summary": "...",
    "source": "...",
    "url": "..."
  }
]
```

## tech-indicator

### Recommended Indicators

Keep only the most interpretable first:

| Indicator | Reason |
|---|---|
| MA/EMA | Trend |
| RSI | Momentum |
| MACD | Momentum shift |
| Bollinger Bands | Volatility |
| ATR | Risk/volatility |
| OBV | Volume confirmation |

Avoid adding 30+ indicators immediately.

## finance-rag

### Purpose
Semantic search over:
- 10-K
- 10-Q
- 8-K

### MVP Recommendation

Use:
```python
ChromaDB
```

Only migrate later if scale requires it.

# 9.5 Error handling
## Error Handling & Graceful Degradation

When a skill fails during a `stock-retro` call, the report should **degrade gracefully**
rather than fail entirely. Each atomic skill is treated as independent — a timeout or
API error in one should not block the others from completing.

### Failure Behavior Per Skill

| Skill | If It Fails | Report Impact |
|---|---|---|
| `market-data` | Abort — this is non-negotiable | Cannot produce report without price data |
| `web-access` | Degrade — skip news section | Note: "News unavailable at time of report" |
| `tech-indicator` | Degrade — skip signals section | Note: "Technical signals could not be computed" |
| `finance-rag` | Degrade — skip filing highlights | Note: "SEC filing search unavailable" |

### Implementation Pattern

Each skill should return a structured result envelope rather than raising raw exceptions:

```python
{
  "status": "success" | "degraded" | "failed",
  "data": { ... },
  "error": "timeout after 10s" | None,
  "source": "web-access"
}
```

The `stock-retro` composite skill checks each envelope before passing context to the
LLM synthesis step. Degraded results are passed as explicit gaps — the LLM is instructed
to acknowledge missing sections rather than infer or hallucinate them.

### LLM Prompt Instruction (add to synthesis prompt)

> "If a data section is marked UNAVAILABLE, explicitly state it is missing in that
> section of the report. Do not infer, estimate, or fill in missing data."

# 10. view-validator (Important Redesign)

This should become one of the strongest features.

## Input

```text
"NVIDIA will outperform due to AI demand"
Ticker: NVDA
Timeframe: 6 months
```

## Process

1. Extract thesis direction
2. Pull historical price data
3. Compare performance
4. Measure:
   - return
   - drawdown
   - volatility
   - benchmark comparison

## Output

```text
Verdict:
The thesis was directionally correct.

Metrics:
- Return: +18%
- Max drawdown: -7%
- Sharpe ratio: 1.2
- Relative vs SPY: +9%
```

This feature is:
- explainable
- interview-friendly
- academically defensible

# 11. ML Guidance (Simplified)

## Important Recommendation

Do NOT prioritize deep learning first.

For MVP:
- gradient boosting
- XGBoost
- LightGBM

are more practical and interpretable than:
- LSTM
- GRU
- transformers

## Recommended First Features

```python
returns
rolling volatility
RSI
MACD
moving averages
volume changes
```

Avoid:
- 40+ engineered features initially
- excessive sequence complexity

# 12. Data Leakage Rule (Critical)

Always:

```python
scaler.fit(X_train)

X_train = scaler.transform(X_train)
X_test  = scaler.transform(X_test)
```

Never fit on:

```python
X_all
```

# 13. Metrics That Matter

Do NOT emphasize raw accuracy.

Use:

| Metric | Why |
|---|---|
| Sharpe ratio | Risk-adjusted performance |
| Max drawdown | Worst-case loss |
| Win rate | Consistency |
| Balanced accuracy | Class imbalance |
| Macro F1 | Multi-class fairness |

# 14. Suggested Tech Stack

## Backend

```text
FastAPI
LangGraph
Python
```

## Data

```text
yfinance
SEC EDGAR
NewsAPI
```

## Vector DB

```text
ChromaDB
```

## UI

```text
Streamlit (prototype)
Next.js (production)
```

## LLM

```text
Claude
GPT-4o
```

# 15. Recommended Deployment Strategy

## Phase 1

Single EC2 instance:
- FastAPI
- Streamlit
- ChromaDB

## Phase 2

Split:
- frontend
- backend
- vector database

# 16. Portfolio Presentation Advice

The strongest portfolio framing is:

## Good Framing

> “Built a citation-aware financial research agent that integrates SEC filings, market data, technical indicators, and news synthesis using LangGraph and LLM orchestration.”

## Weak Framing

> “Built an AI stock predictor that tells users what to buy.”

The first sounds:
- credible
- professional
- technically mature

The second sounds:
- risky
- overpromising
- difficult to trust

# 17. Final Recommended Development Order

## Phase 1
- market-data
- web-access
- tech-indicator

## Phase 2
- stock-retro
- synthesis prompts
- citations

## Phase 3
- confidence gate
- view-validator

## Phase 4
- finance-rag

## Phase 5
- options-flow
- macro-context
- advanced ML

# 18. Key Takeaway

The strongest version of this project is NOT:

> “an AI that predicts stocks”

The strongest version is:

> “a transparent, citation-aware financial research system that helps users interpret evidence and understand uncertainty.”
