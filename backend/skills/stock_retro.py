import asyncio
import os
import re
from datetime import datetime, timezone

from openai import AsyncOpenAI

from backend.models.citation import SkillResult
from backend.models.report import ContextBundle, EvidenceBlock, EvidenceCitation, ReportOutput
from backend.prompts.synthesis import SYSTEM_PROMPT, build_user_message
from backend.skills.confidence_score import compute_confidence
from backend.skills.finance_rag import query_sec_filings
from backend.skills.market_data import fetch_market_data
from backend.skills.tech_indicator import compute_indicators
from backend.skills.web_access import fetch_news
from backend.utils.cache import get_cached, set_cached

_WINDOW_TO_DAYS = {"7d": 7, "30d": 30, "90d": 90}


def _price_blocks(result: dict, idx: int) -> tuple[list[EvidenceBlock], int]:
    data = result["data"]
    summary = data["summary"]
    ticker = data["ticker"]
    window = data["window"]
    latest_date = data["ohlcv"][-1]["date"]

    content = (
        f"{ticker} closed at ${summary['latest_close']} on {latest_date}, "
        f"{summary['return_pct']:+.1f}% over the {window} window. "
        f"MA20: {summary['ma_20']}, MA50: {summary['ma_50']}, MA200: {summary['ma_200']}. "
        f"Average volume: {summary['avg_volume']:,}. "
        f"Annualised volatility: {summary['volatility_ann_pct']}%."
    )
    block = EvidenceBlock(
        citation_index=idx,
        source_type="price_data",
        content=content,
        citation=EvidenceCitation(source_name="Polygon.io", url=None, date=latest_date),
    )
    return [block], idx + 1


def _tech_blocks(result: dict, idx: int) -> tuple[list[EvidenceBlock], int]:
    if result["status"] != "success":
        block = EvidenceBlock(
            citation_index=idx,
            source_type="technical",
            content=f"UNAVAILABLE — {result.get('error', 'indicators could not be computed')}",
            citation=None,
        )
        return [block], idx + 1

    ind = result["data"]["indicators"]
    rsi = ind.get("rsi_14")
    rsi_note = (
        "overbought" if rsi is not None and rsi > 70
        else "oversold" if rsi is not None and rsi < 30
        else "neutral"
    )
    macd_h = ind.get("macd_histogram")
    macd_note = (
        "expanding positively" if macd_h is not None and macd_h > 0
        else "expanding negatively"
    )

    content = (
        f"RSI(14): {rsi} ({rsi_note}). "
        f"MACD: {ind.get('macd')}, Signal: {ind.get('macd_signal')}, "
        f"Histogram: {macd_h} ({macd_note}). "
        f"Bollinger Bands — Upper: {ind.get('bb_upper')}, Mid: {ind.get('bb_mid')}, "
        f"Lower: {ind.get('bb_lower')}. "
        f"ATR(14): {ind.get('atr_14')}. OBV: {ind.get('obv')}. "
        f"EMA20: {ind.get('ema_20')}, EMA50: {ind.get('ema_50')}."
    )
    cit = result.get("citations", [{}])[0]
    block = EvidenceBlock(
        citation_index=idx,
        source_type="technical",
        content=content,
        citation=EvidenceCitation(
            source_name=cit.get("source_name", "Polygon.io / pandas-ta"),
            url=None,
            date=cit.get("date", datetime.now().strftime("%Y-%m-%d")),
        ),
    )
    return [block], idx + 1


def _news_blocks(result: dict, idx: int) -> tuple[list[EvidenceBlock], int]:
    if result["status"] != "success":
        block = EvidenceBlock(
            citation_index=idx,
            source_type="news",
            content=f"UNAVAILABLE — {result.get('error', 'web-access timed out')}",
            citation=None,
        )
        return [block], idx + 1

    blocks = []
    articles = result["data"]["articles"]
    for i, article in enumerate(articles):
        content = f"{article['title']}. {article.get('summary') or ''}".strip(". ")
        blocks.append(EvidenceBlock(
            citation_index=idx + i,
            source_type="news",
            content=content,
            citation=EvidenceCitation(
                source_name=article.get("source") or "Unknown",
                url=article.get("url"),
                date=article.get("date") or "",
            ),
        ))
    return blocks, idx + len(articles)


_TIER_FALLBACK_SCORES = {"high": 75.0, "moderate": 52.0, "low": 39.0, "very low": 20.0}


def _extract_confidence(text: str) -> float | None:
    # Primary: first percentage following "confidence" on the same line, tolerating an
    # intervening tier label, e.g. "Confidence: Moderate (50%)" or "Confidence: 50%".
    match = re.search(r'[Cc]onfidence[^\n%]*?(\d+(?:\.\d+)?)\s*%', text)
    if match:
        return float(match.group(1))
    # Fallback: map a tier word to a representative score when no number is given.
    tier = re.search(r'[Cc]onfidence[^\n]*?(Very Low|High|Moderate|Low)', text)
    if tier:
        return _TIER_FALLBACK_SCORES[tier.group(1).lower()]
    return None


async def run_stock_retro(
    ticker: str,
    window: str = "7d",
    company_name: str | None = None,
) -> dict:
    ticker = ticker.upper()
    days = _WINDOW_TO_DAYS.get(window, 7)
    generated_at = datetime.now(timezone.utc).isoformat()

    cached = await get_cached(f"report:{ticker}:{window}:{company_name or ''}")
    if cached is not None:
        return cached

    # market-data and news run concurrently; tech-indicator needs market-data output
    market_result, news_result = await asyncio.gather(
        fetch_market_data(ticker, window),
        fetch_news(ticker, company_name, days=days),
    )

    if market_result["status"] == "failed":
        return SkillResult(
            status="failed",
            error=f"market-data failed — cannot produce report: {market_result.get('error')}",
            source="stock-retro",
        ).model_dump()

    sec_query = f"{ticker} business risks outlook revenue earnings"
    tech_result, rag_result = await asyncio.gather(
        compute_indicators(ticker, market_result["data"]["full_history"]),
        query_sec_filings(ticker, sec_query, top_k=5),
    )

    confidence = compute_confidence(market_result, tech_result, news_result, rag_result)

    # Assemble ContextBundle with sequential citation_index values
    evidence: list[EvidenceBlock] = []
    idx = 0

    price_blocks, idx = _price_blocks(market_result, idx)
    evidence.extend(price_blocks)

    tech_blks, idx = _tech_blocks(tech_result, idx)
    evidence.extend(tech_blks)

    news_blks, idx = _news_blocks(news_result, idx)
    evidence.extend(news_blks)

    if rag_result["status"] == "success":
        for raw_block in rag_result["data"]["blocks"]:
            evidence.append(EvidenceBlock(
                citation_index=idx,
                source_type=raw_block["source_type"],
                content=raw_block["content"],
                citation=EvidenceCitation(**raw_block["citation"]) if raw_block.get("citation") else None,
            ))
            idx += 1

    bundle = ContextBundle(
        ticker=ticker,
        window=window,
        generated_at=generated_at,
        evidence=evidence,
    )

    # LLM synthesis
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    try:
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_message(bundle, confidence)},
            ],
            temperature=0.2,
        )
        report_text = response.choices[0].message.content
    except Exception as e:
        return SkillResult(
            status="failed",
            error=f"LLM synthesis failed: {e}",
            source="stock-retro",
        ).model_dump()

    output = ReportOutput(
        ticker=ticker,
        window=window,
        generated_at=generated_at,
        report_text=report_text,
        evidence=evidence,
        confidence_score=confidence["score"],
        confidence_breakdown=confidence["breakdown"],
    )

    result = SkillResult(
        status="success",
        data=output.model_dump(),
        source="stock-retro",
    ).model_dump()
    await set_cached(f"report:{ticker}:{window}:{company_name or ''}", result, ttl_seconds=4 * 3600)
    return result