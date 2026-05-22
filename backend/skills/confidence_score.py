"""
Deterministic, evidence-based confidence score.

Replaces the LLM's self-reported confidence (which clustered on round numbers)
with a number computed from measurable signals: how complete the evidence is,
whether the technical signals agree on a direction, and how much corroborating
evidence was retrieved. Score is on a 0-100 scale and feeds the confidence gate.

Component weights (sum to 100):
  - data completeness   (40): price / technical / SEC / news availability
  - signal coherence    (35): agreement among technical+price direction signals
  - evidence depth       (25): volume of SEC chunks and news articles
"""

from backend.skills.confidence_gate import get_confidence_tier


def _technical_votes(summary: dict, indicators: dict) -> tuple[int, int]:
    bull = bear = 0
    close = summary.get("latest_close")

    ret = summary.get("return_pct")
    if ret is not None:
        if ret > 0:
            bull += 1
        elif ret < 0:
            bear += 1

    for ma_key in ("ma_20", "ma_50", "ma_200"):
        ma = summary.get(ma_key)
        if close is not None and ma:
            if close > ma:
                bull += 1
            elif close < ma:
                bear += 1

    hist = indicators.get("macd_histogram")
    if hist is not None:
        if hist > 0:
            bull += 1
        elif hist < 0:
            bear += 1

    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if rsi < 30:
            bull += 1
        elif rsi > 70:
            bear += 1

    ema_20, ema_50 = indicators.get("ema_20"), indicators.get("ema_50")
    if ema_20 is not None and ema_50 is not None:
        if ema_20 > ema_50:
            bull += 1
        elif ema_20 < ema_50:
            bear += 1

    return bull, bear


def compute_confidence(
    market_result: dict,
    tech_result: dict,
    news_result: dict,
    rag_result: dict,
) -> dict:
    """Compute a 0-100 confidence score with an explainable breakdown from the
    raw skill-result envelopes assembled by stock-retro."""
    price_ok = market_result.get("status") == "success"
    tech_ok = tech_result.get("status") == "success"
    sec_ok = rag_result.get("status") == "success"
    news_ok = news_result.get("status") == "success"

    n_chunks = len(rag_result.get("data", {}).get("blocks", [])) if sec_ok else 0
    n_articles = len(news_result.get("data", {}).get("articles", [])) if news_ok else 0

    # Data completeness (max 40)
    completeness = 0.0
    if price_ok:
        completeness += 10
    if tech_ok:
        completeness += 10
    if sec_ok and n_chunks > 0:
        completeness += 10
    completeness += 10 * min(n_articles, 3) / 3

    # Signal coherence (max 35) — how decisively the signals point one way
    coherence = 0.0
    bull = bear = 0
    if price_ok and tech_ok:
        bull, bear = _technical_votes(
            market_result["data"]["summary"],
            tech_result["data"]["indicators"],
        )
        total = bull + bear
        if total > 0:
            ratio = max(bull, bear) / total  # 0.5 (split) .. 1.0 (unanimous)
            coherence = 35 * (ratio - 0.5) / 0.5

    # Evidence depth (max 25)
    depth = 15 * min(n_chunks, 5) / 5 + 10 * min(n_articles, 5) / 5

    score = max(0.0, min(100.0, round(completeness + coherence + depth, 1)))
    direction = "bullish" if bull > bear else "bearish" if bear > bull else "mixed"

    return {
        "score": score,
        "tier": get_confidence_tier(score),
        "breakdown": {
            "data_completeness": round(completeness, 1),
            "signal_coherence": round(coherence, 1),
            "evidence_depth": round(depth, 1),
            "technical_bias": direction,
            "signals_bull": bull,
            "signals_bear": bear,
            "news_articles": n_articles,
            "sec_chunks": n_chunks,
        },
    }