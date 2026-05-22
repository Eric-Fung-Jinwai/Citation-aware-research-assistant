import asyncio
import os
import re
from datetime import datetime, timedelta

import httpx
import pandas as pd
from openai import AsyncOpenAI

from backend.models.citation import CitationObject, SkillResult
from backend.utils.dates import last_trading_day

POLYGON_BASE = "https://api.polygon.io"

_TIMEFRAME_DAYS: dict[str, int] = {
    "1m": 30,  "1month": 30,  "1 month": 30,
    "3m": 90,  "3months": 90, "3 months": 90,
    "6m": 180, "6months": 180, "6 months": 180,
    "1y": 365, "1year": 365,  "1 year": 365,
    "2y": 730, "2years": 730, "2 years": 730,
}


def _parse_timeframe(timeframe: str) -> int:
    normalized = timeframe.lower().strip()
    if normalized in _TIMEFRAME_DAYS:
        return _TIMEFRAME_DAYS[normalized]
    m = re.match(r"(\d+)\s*(day|days|d|month|months|m|year|years|y)", normalized)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        if unit.startswith("d"):
            return n
        if unit.startswith("m"):
            return n * 30
        if unit.startswith("y"):
            return n * 365
    return 180


async def _fetch_closes(ticker: str, from_dt: datetime, to_dt: datetime) -> pd.Series | None:
    """
    Fetch adjusted daily closes between from_dt and to_dt (inclusive).
    Returns a Series indexed by tz-naive date, sorted ascending.
    """
    api_key = os.getenv("POLYGON_API_KEY")
    url = (
        f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/day"
        f"/{from_dt.strftime('%Y-%m-%d')}/{to_dt.strftime('%Y-%m-%d')}"
    )
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url, params={"apiKey": api_key, "adjusted": "true", "sort": "asc"}
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
    except Exception:
        return None

    if not results:
        return None

    df = pd.DataFrame(results)
    df["date"] = pd.to_datetime(df["t"], unit="ms").dt.normalize()
    return df.set_index("date")["c"].sort_index()


def _align(s1: pd.Series, s2: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Restrict both series to their shared trading dates."""
    shared = s1.index.intersection(s2.index)
    return s1[shared], s2[shared]


def _compute_metrics(prices: pd.Series) -> dict:
    if len(prices) < 2:
        return {"total_return_pct": None, "max_drawdown_pct": None, "sharpe_ratio": None}

    total_return = (prices.iloc[-1] / prices.iloc[0] - 1) * 100

    daily_returns = prices.pct_change().dropna()
    cumulative = (1 + daily_returns).cumprod()
    drawdown = (cumulative - cumulative.cummax()) / cumulative.cummax()
    max_drawdown = drawdown.min() * 100

    sharpe = None
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe = round(float(daily_returns.mean() / daily_returns.std()) * (252 ** 0.5), 2)

    return {
        "total_return_pct": round(float(total_return), 2),
        "max_drawdown_pct": round(float(max_drawdown), 2),
        "sharpe_ratio": sharpe,
    }


async def _extract_direction(thesis: str, client: AsyncOpenAI) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You extract the directional investment stance from a thesis. "
                    "Reply with exactly one word: 'bullish', 'bearish', or 'unknown'. Nothing else."
                ),
            },
            {"role": "user", "content": thesis},
        ],
        temperature=0,
        max_tokens=5,
    )
    direction = response.choices[0].message.content.strip().lower()
    return direction if direction in ("bullish", "bearish") else "unknown"


async def validate_view(
    thesis: str,
    ticker: str,
    timeframe: str = "6 months",
) -> dict:
    """
    Evaluate a directional thesis against historical price data.

    NOTE: Always evaluates the most recent `timeframe` window ending today.
    Backtesting from a specific start date requires a future `as_of` parameter.

    Bearish correctness uses relative performance: the thesis is correct if the
    stock underperformed SPY over the period. Falls back to absolute negative
    return if SPY data is unavailable.
    """
    ticker = ticker.upper()
    days = _parse_timeframe(timeframe)
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    to_dt = last_trading_day()
    from_dt = to_dt - timedelta(days=days)

    try:
        direction, ticker_prices, spy_prices = await asyncio.gather(
            _extract_direction(thesis, client),
            _fetch_closes(ticker, from_dt, to_dt),
            _fetch_closes("SPY", from_dt, to_dt),
        )
    except Exception as e:
        return SkillResult(
            status="failed",
            error=f"view-validator failed: {e}",
            source="view-validator",
        ).model_dump()

    if ticker_prices is None or len(ticker_prices) < 2:
        return SkillResult(
            status="failed",
            error=f"Insufficient price data for {ticker} over the requested timeframe.",
            source="view-validator",
        ).model_dump()

    # Align to shared trading dates so returns are computed on identical periods
    if spy_prices is not None and len(spy_prices) >= 2:
        ticker_prices, spy_prices = _align(ticker_prices, spy_prices)
    else:
        spy_prices = None

    ticker_metrics = _compute_metrics(ticker_prices)
    spy_metrics = _compute_metrics(spy_prices) if spy_prices is not None else None

    ticker_return = ticker_metrics["total_return_pct"]
    spy_return = spy_metrics["total_return_pct"] if spy_metrics else None

    # Bullish: positive absolute return.
    # Bearish: underperformed SPY (relative); falls back to absolute negative if SPY unavailable.
    if direction == "bullish":
        directionally_correct = ticker_return is not None and ticker_return > 0
    elif direction == "bearish":
        if spy_return is not None:
            directionally_correct = ticker_return is not None and ticker_return < spy_return
        else:
            directionally_correct = ticker_return is not None and ticker_return < 0
    else:
        directionally_correct = None

    if directionally_correct is True:
        verdict = "The thesis was directionally correct."
    elif directionally_correct is False:
        verdict = "The thesis was directionally incorrect."
    else:
        verdict = "Direction could not be determined from the thesis."

    relative_vs_spy = (
        round(ticker_return - spy_return, 2)
        if ticker_return is not None and spy_return is not None
        else None
    )

    from_str = from_dt.strftime("%Y-%m-%d")
    to_str = to_dt.strftime("%Y-%m-%d")

    citation = CitationObject(
        claim=f"{ticker} returned {ticker_return:+.1f}% from {from_str} to {to_str}.",
        source_type="price_data",
        source_name="Polygon.io",
        url=None,
        date=to_str,
        excerpt=(
            f"{ticker}: {ticker_return:+.1f}% total return over {timeframe}. "
            + (
                f"SPY: {spy_return:+.1f}%. Relative to SPY: {relative_vs_spy:+.1f}%."
                if spy_return is not None
                else "SPY benchmark data unavailable."
            )
        ),
    )

    return SkillResult(
        status="success",
        data={
            "ticker": ticker,
            "timeframe": timeframe,
            "from_date": from_str,
            "to_date": to_str,
            "thesis": thesis,
            "direction": direction,
            "verdict": verdict,
            "metrics": {
                "total_return_pct": ticker_return,
                "max_drawdown_pct": ticker_metrics["max_drawdown_pct"],
                "sharpe_ratio": ticker_metrics["sharpe_ratio"],
                "spy_return_pct": spy_return,
                "relative_vs_spy_pct": relative_vs_spy,
            },
        },
        citations=[citation],
        source="view-validator",
    ).model_dump()