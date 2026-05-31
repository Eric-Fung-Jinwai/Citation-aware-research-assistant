"""
pytest suite for Phases 0-4 of the Stock Analysis System.

Two tiers:
  * Offline tests (citation models/parser, confidence gate, synthetic indicators)
    run on a plain `pytest` — fast, free, no keys or network.
  * Live tests (@pytest.mark.live) hit Polygon / NewsAPI / OpenAI / SEC EDGAR and
    are skipped unless RUN_LIVE=1, so a normal run never burns API credits.

Run:
    pytest smoke_test.py                 # offline tests only
    RUN_LIVE=1 pytest smoke_test.py      # everything (needs keys in .env)
    RUN_LIVE=1 pytest smoke_test.py -m live   # only the live tests
"""
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

RUN_LIVE = os.getenv("RUN_LIVE") == "1"
requires_live = pytest.mark.skipif(not RUN_LIVE, reason="live test; set RUN_LIVE=1 to run")


def _have(key: str) -> bool:
    v = os.getenv(key)
    return bool(v and v.strip() and "your_" not in v.lower())


def _require(*keys: str) -> None:
    missing = [k for k in keys if not _have(k)]
    if missing:
        pytest.skip(f"missing {', '.join(missing)}")


# ----------------------------------------------------------------------------
# Offline — always run (no keys, no network)
# ----------------------------------------------------------------------------
def test_citation_models():
    from backend.models.citation import CitationObject, SkillResult
    from backend.models.report import ContextBundle, EvidenceBlock, EvidenceCitation

    c = CitationObject(claim="x", source_type="news", source_name="S", date="2026-01-01", excerpt="e")
    dumped = SkillResult(status="success", data={"a": 1}, citations=[c], source="t").model_dump()
    assert dumped["status"] == "success"
    assert dumped["citations"][0]["claim"] == "x"

    eb = EvidenceBlock(
        citation_index=0,
        source_type="price_data",
        content="c",
        citation=EvidenceCitation(source_name="Polygon.io", date="2026-01-01"),
    )
    bundle = ContextBundle(ticker="AAPL", window="7d", generated_at="2026-01-01T00:00:00Z", evidence=[eb])
    assert bundle.evidence[0].citation_index == 0


def test_citation_parser():
    from backend.utils.citation_parser import parse_citations

    clean, footnotes = parse_citations(
        "Foo [cite:0] bar [cite:2] baz [cite:0].", {0: {"source_name": "A"}, 2: {"source_name": "B"}}
    )
    assert clean == "Foo [1] bar [2] baz [1]."
    assert len(footnotes) == 2  # duplicate [cite:0] collapses to one footnote


def test_confidence_gate():
    from backend.skills.confidence_gate import apply_confidence_gate, get_confidence_tier

    assert get_confidence_tier(75) == "High"
    assert get_confidence_tier(50) == "Moderate"
    assert get_confidence_tier(40) == "Low"
    assert get_confidence_tier(20) == "Very Low"

    base = {"status": "success", "data": {"confidence_score": 70.0, "report_text": "..."}, "source": "stock-retro"}
    assert apply_confidence_gate(base)["data"]["confidence_tier"] == "High"
    assert apply_confidence_gate({**base, "data": {**base["data"], "confidence_score": 20.0}})["status"] == "blocked"
    assert apply_confidence_gate({**base, "data": {"report_text": "no score"}})["data"]["confidence_tier"] == "Unknown"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Confidence: 55%", 55.0),
        ("Confidence: Moderate (50%)", 50.0),
        ("**Confidence:** 72%", 72.0),
        ("Confidence: High", 75.0),       # tier-word fallback
        ("Confidence: Very Low", 20.0),   # tier-word fallback
        ("no score here", None),
    ],
)
def test_extract_confidence(text, expected):
    from backend.skills.stock_retro import _extract_confidence

    assert _extract_confidence(text) == expected


async def test_cache_round_trip():
    """Offline — mock Redis client, no live Redis needed."""
    from unittest.mock import AsyncMock, patch
    import backend.utils.cache as cache_mod

    store: dict = {}

    async def _get(key):
        return store.get(key)

    async def _set(key, value, ex=None):
        store[key] = value

    mock_client = AsyncMock()
    mock_client.get = _get
    mock_client.set = _set

    with patch.object(cache_mod, "_redis", new=AsyncMock(return_value=mock_client)):
        assert await cache_mod.get_cached("k") is None          # miss
        await cache_mod.set_cached("k", {"score": 42}, ttl_seconds=300)
        assert await cache_mod.get_cached("k") == {"score": 42}  # hit


async def test_cache_unavailable_redis():
    """Offline — cache silently no-ops when Redis is unreachable."""
    from unittest.mock import AsyncMock, patch
    import backend.utils.cache as cache_mod

    with patch.object(cache_mod, "_redis", new=AsyncMock(return_value=None)):
        assert await cache_mod.get_cached("k") is None
        await cache_mod.set_cached("k", {"x": 1}, ttl_seconds=60)  # must not raise


async def test_tech_indicator_synthetic():
    """Offline — also proves pandas-ta actually computes on this arch."""
    from backend.skills.tech_indicator import compute_indicators

    random.seed(42)
    rows, price, d = [], 100.0, date(2025, 1, 1)
    for i in range(210):
        price *= 1 + random.uniform(-0.02, 0.02)
        o = price * (1 + random.uniform(-0.01, 0.01))
        rows.append({
            "date": (d + timedelta(days=i)).isoformat(),
            "open": round(o, 2),
            "high": round(max(o, price) * (1 + random.uniform(0, 0.01)), 2),
            "low": round(min(o, price) * (1 - random.uniform(0, 0.01)), 2),
            "close": round(price, 2),
            "volume": random.randint(1_000_000, 5_000_000),
        })

    res = await compute_indicators("TEST", rows)
    assert res["status"] == "success", res.get("error")
    ind = res["data"]["indicators"]
    assert ind["rsi_14"] is not None
    assert ind["macd"] is not None
    assert ind["ema_50"] is not None


# ----------------------------------------------------------------------------
# Live — skipped unless RUN_LIVE=1
# ----------------------------------------------------------------------------
@pytest.mark.live
@requires_live
async def test_market_data():
    _require("POLYGON_API_KEY")
    from backend.skills.market_data import fetch_market_data

    res = await fetch_market_data("AAPL", "30d")
    assert res["status"] == "success", res.get("error")
    s = res["data"]["summary"]
    assert s["latest_close"] is not None
    assert s["ma_200"] is not None  # regression guard: fetch window must cover 200 trading days


@pytest.mark.live
@requires_live
async def test_tech_indicator_real():
    _require("POLYGON_API_KEY")
    from backend.skills.market_data import fetch_market_data
    from backend.skills.tech_indicator import compute_indicators

    mkt = await fetch_market_data("AAPL", "30d")
    assert mkt["status"] == "success", mkt.get("error")
    res = await compute_indicators("AAPL", mkt["data"]["full_history"])
    assert res["status"] == "success", res.get("error")
    assert res["data"]["indicators"]["rsi_14"] is not None


@pytest.mark.live
@requires_live
async def test_web_access():
    _require("NEWS_API_KEY")
    from backend.skills.web_access import fetch_news

    res = await fetch_news("AAPL", "Apple", days=7)
    if res["status"] == "degraded":
        pytest.skip(f"web-access degraded (external/key issue): {res.get('error')}")
    assert res["status"] == "success"
    assert len(res["data"]["articles"]) >= 1


@pytest.mark.live
@requires_live
async def test_stock_retro_and_gate():
    _require("POLYGON_API_KEY", "OPENAI_API_KEY")
    from backend.skills.confidence_gate import apply_confidence_gate
    from backend.skills.stock_retro import run_stock_retro

    res = await run_stock_retro("AAPL", "30d", company_name="Apple")
    assert res["status"] == "success", res.get("error")
    assert "[cite:" in res["data"]["report_text"]  # LLM emitted citation tags
    assert res["data"]["confidence_score"] is not None  # regression guard: confidence parses

    gated = apply_confidence_gate(res)
    assert gated["status"] in ("success", "blocked")


@pytest.mark.live
@requires_live
async def test_view_validator():
    _require("POLYGON_API_KEY", "OPENAI_API_KEY")
    from backend.skills.view_validator import validate_view

    res = await validate_view("AAPL will outperform on strong iPhone demand", "AAPL", "3 months")
    assert res["status"] == "success", res.get("error")
    assert res["data"]["direction"] in ("bullish", "bearish", "unknown")
    assert res["data"]["metrics"]["total_return_pct"] is not None


@pytest.mark.live
@requires_live
async def test_finance_rag():
    from backend.skills.finance_rag import query_sec_filings

    res = await query_sec_filings("AAPL", "revenue growth and business risks", top_k=3)
    if res["status"] == "degraded":
        pytest.skip(f"finance-rag degraded: {res.get('error')}")
    assert res["status"] == "success"
    assert len(res["data"]["blocks"]) >= 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
