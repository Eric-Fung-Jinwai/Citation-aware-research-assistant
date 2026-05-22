from typing import Callable

import streamlit as st

_TIMEFRAMES = ["1 month", "3 months", "6 months", "1 year", "2 years"]


def _pct(value: float | None) -> str:
    return f"{value:+.2f}%" if value is not None else "—"


def _render_result(result: dict) -> None:
    if result.get("status") != "success":
        st.error(result.get("error", "View validation failed."))
        return

    data = result["data"]
    verdict = data["verdict"]

    if "incorrect" in verdict:
        st.warning(verdict)
    elif "correct" in verdict:
        st.success(verdict)
    else:
        st.info(verdict)

    st.caption(
        f"Direction extracted: {data['direction']} · "
        f"{data['from_date']} → {data['to_date']}"
    )

    m = data["metrics"]
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{data['ticker']} return", _pct(m["total_return_pct"]))
    c2.metric("Max drawdown", _pct(m["max_drawdown_pct"]))
    c3.metric("Sharpe", m["sharpe_ratio"] if m["sharpe_ratio"] is not None else "—")

    if m.get("spy_return_pct") is not None:
        c4, c5 = st.columns(2)
        c4.metric("SPY return", _pct(m["spy_return_pct"]))
        c5.metric("vs SPY", _pct(m["relative_vs_spy_pct"]))

    for cit in result.get("citations", []):
        if cit.get("excerpt"):
            st.caption(cit["excerpt"])


def render_validator_panel(call_validate: Callable[[str, str, str], dict]) -> None:
    """Render the view-validator form and result. `call_validate(thesis, ticker, timeframe)`
    performs the backend call and returns the response envelope."""
    st.write("Test a directional thesis against historical price performance vs SPY.")

    with st.form("validate_form"):
        thesis = st.text_area(
            "Thesis",
            placeholder="NVDA will outperform on continued AI datacenter demand.",
        )
        c1, c2 = st.columns(2)
        ticker = c1.text_input("Ticker", placeholder="NVDA").strip().upper()
        timeframe = c2.selectbox("Timeframe", _TIMEFRAMES, index=2)
        submitted = st.form_submit_button("Validate")

    if not submitted:
        return

    if not thesis.strip() or not ticker:
        st.warning("Enter both a thesis and a ticker.")
        return

    with st.spinner("Backtesting thesis..."):
        result = call_validate(thesis.strip(), ticker, timeframe)
    _render_result(result)