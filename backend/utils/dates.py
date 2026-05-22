from datetime import datetime, timedelta

import pandas_market_calendars as mcal

# Initialised once at import time — mirrors Tushare's trade_cal pattern
# from the A-share reference project, adapted for NYSE.
_nyse = mcal.get_calendar("NYSE")


def last_trading_day(date: datetime | None = None, lookback_days: int = 14) -> datetime:
    """
    Return the most recent NYSE trading day on or before the given date.

    Handles weekends AND all US market holidays (NYSE calendar).
    lookback_days gives enough buffer to survive long holiday windows
    (e.g. Christmas + New Year stretch).

    Raises ValueError if no trading day is found in the lookback window,
    which should never happen in practice with the default 14-day buffer.
    """
    d = (date or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    start = d - timedelta(days=lookback_days)

    schedule = _nyse.schedule(
        start_date=start.strftime("%Y-%m-%d"),
        end_date=d.strftime("%Y-%m-%d"),
    )

    if schedule.empty:
        raise ValueError(
            f"No NYSE trading days found between {start.date()} and {d.date()}. "
            "Try increasing lookback_days."
        )

    last_open = schedule.index[-1].to_pydatetime().replace(tzinfo=None)

    if last_open.date() != d.date():
        print(f"[dates] {d.date()} is not a trading day — using {last_open.date()} instead.")

    return last_open