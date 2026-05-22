import math
from datetime import datetime

import pandas as pd
import pandas_ta as ta

from backend.models.citation import CitationObject, SkillResult


def _safe(val) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else round(f, 4)
    except (TypeError, ValueError):
        return None


async def compute_indicators(ticker: str, ohlcv_records: list[dict]) -> dict:
    if not ohlcv_records:
        return SkillResult(
            status="failed",
            error="No OHLCV data provided to tech-indicator",
            source="tech-indicator",
        ).model_dump()

    try:
        df = pd.DataFrame(ohlcv_records)
        # pandas-ta expects lowercase column names: open, high, low, close, volume
        df = df[["date", "open", "high", "low", "close", "volume"]].copy()

        df.ta.rsi(length=14, append=True)
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.atr(length=14, append=True)
        df.ta.obv(append=True)
        df.ta.ema(length=20, append=True)
        df.ta.ema(length=50, append=True)

        latest = df.iloc[-1]
        today = datetime.now().strftime("%Y-%m-%d")

        indicators = {
            "rsi_14": _safe(latest.get("RSI_14")),
            "macd": _safe(latest.get("MACD_12_26_9")),
            "macd_signal": _safe(latest.get("MACDs_12_26_9")),
            "macd_histogram": _safe(latest.get("MACDh_12_26_9")),
            "bb_upper": _safe(latest.get("BBU_20_2.0")),
            "bb_mid": _safe(latest.get("BBM_20_2.0")),
            "bb_lower": _safe(latest.get("BBL_20_2.0")),
            "atr_14": _safe(latest.get("ATRr_14")),
            "obv": _safe(latest.get("OBV")),
            "ema_20": _safe(latest.get("EMA_20")),
            "ema_50": _safe(latest.get("EMA_50")),
        }

        rsi = indicators["rsi_14"]
        if rsi is not None:
            rsi_note = "overbought" if rsi > 70 else "oversold" if rsi < 30 else "neutral"
        else:
            rsi_note = "unavailable"

        macd_h = indicators["macd_histogram"]
        if macd_h is not None:
            macd_note = "expanding positively" if macd_h > 0 else "expanding negatively"
        else:
            macd_note = "unavailable"

        excerpt = (
            f"RSI(14): {rsi} ({rsi_note}). "
            f"MACD histogram {macd_note} ({macd_h}). "
            f"ATR(14): {indicators['atr_14']}. "
            f"EMA20: {indicators['ema_20']}, EMA50: {indicators['ema_50']}."
        )

        citation = CitationObject(
            claim=f"{ticker} technical indicators as of {today}: RSI {rsi} ({rsi_note}), MACD histogram {macd_note}.",
            source_type="technical",
            source_name="Polygon.io / pandas-ta",
            url=None,
            date=today,
            excerpt=excerpt,
        )

        return SkillResult(
            status="success",
            data={"ticker": ticker, "indicators": indicators},
            citations=[citation],
            source="tech-indicator",
        ).model_dump()

    except Exception as e:
        return SkillResult(
            status="degraded",
            error=f"Indicator computation failed: {e}",
            source="tech-indicator",
        ).model_dump()