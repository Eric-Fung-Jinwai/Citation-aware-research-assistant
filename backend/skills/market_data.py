import os
import math
from datetime import datetime, timedelta

import httpx
import pandas as pd

from backend.models.citation import CitationObject, SkillResult
from backend.utils.dates import last_trading_day

POLYGON_BASE = "https://api.polygon.io"

WINDOW_DAYS = {"7d": 7, "30d": 30, "90d": 90}


async def fetch_market_data(
    ticker: str, window: str = "7d", as_of: datetime | None = None
) -> dict:
    api_key = os.getenv("POLYGON_API_KEY")
    window_days = WINDOW_DAYS.get(window, 7)

    # Snap to last trading day in case user passes a weekend or holiday date
    end = last_trading_day(as_of)

    # Fetch ~365 calendar days (~252 trading days) so the 200-day MA can be computed.
    # 200 trading days needs ~290 calendar days, so the old 210 always left ma_200 as NaN.
    fetch_days = max(window_days + 5, 365)
    to_date = end.strftime("%Y-%m-%d")
    from_date = (end - timedelta(days=fetch_days)).strftime("%Y-%m-%d")

    url = f"{POLYGON_BASE}/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                url,
                params={"apiKey": api_key, "adjusted": "true", "sort": "asc"},
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.TimeoutException:
        return SkillResult(
            status="failed",
            error="Polygon.io request timed out after 20s",
            source="market-data",
        ).model_dump()
    except Exception as e:
        return SkillResult(
            status="failed", error=str(e), source="market-data"
        ).model_dump()

    results = payload.get("results", [])
    if not results:
        return SkillResult(
            status="failed",
            error=f"No price data returned for {ticker}",
            source="market-data",
        ).model_dump()

    df = pd.DataFrame(results)
    df["date"] = pd.to_datetime(df["t"], unit="ms").dt.strftime("%Y-%m-%d")
    df = df.rename(
        columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"}
    )

    df["ma_20"] = df["close"].rolling(20).mean()
    df["ma_50"] = df["close"].rolling(50).mean()
    df["ma_200"] = df["close"].rolling(200).mean()

    window_df = df.tail(window_days).copy()
    latest = window_df.iloc[-1]
    first = window_df.iloc[0]

    return_pct = ((latest["close"] - first["close"]) / first["close"]) * 100
    avg_volume = window_df["volume"].mean()
    daily_returns = window_df["close"].pct_change().dropna()
    volatility_ann = daily_returns.std() * (252**0.5) * 100

    def safe(val):
        return None if (val is None or (isinstance(val, float) and math.isnan(val))) else round(float(val), 2)

    ohlcv = window_df[["date", "open", "high", "low", "close", "volume"]].to_dict("records")

    citation = CitationObject(
        claim=f"{ticker} closed at ${latest['close']:.2f} on {latest['date']}, {return_pct:+.1f}% over {window}.",
        source_type="price_data",
        source_name="Polygon.io",
        url=None,
        date=latest["date"],
        excerpt=(
            f"Close: ${latest['close']:.2f}. Volume: {int(latest['volume']):,}. "
            f"{window} return: {return_pct:+.1f}%. Annualised volatility: {volatility_ann:.1f}%."
        ),
    )

    data = {
        "ticker": ticker,
        "window": window,
        "ohlcv": ohlcv,
        # full history passed to tech-indicator so it can compute long-period indicators
        "full_history": df[["date", "open", "high", "low", "close", "volume"]].to_dict("records"),
        "summary": {
            "latest_close": safe(latest["close"]),
            "return_pct": round(float(return_pct), 2),
            "avg_volume": int(avg_volume),
            "volatility_ann_pct": round(float(volatility_ann), 2),
            "ma_20": safe(latest["ma_20"]),
            "ma_50": safe(latest["ma_50"]),
            "ma_200": safe(latest["ma_200"]),
        },
    }

    return SkillResult(
        status="success", data=data, citations=[citation], source="market-data"
    ).model_dump()
