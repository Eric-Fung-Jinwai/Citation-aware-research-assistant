import streamlit as st

_TIER_COLORS = {
    "High": "#1a7f37",
    "Moderate": "#bf8700",
    "Low": "#bc4c00",
    "Very Low": "#cf222e",
    "Unknown": "#6e7781",
}


def render_confidence_badge(
    tier: str,
    score: float | None = None,
    warning: str | None = None,
    breakdown: dict | None = None,
) -> None:
    color = _TIER_COLORS.get(tier, "#6e7781")
    score_txt = f" · {score:.0f}%" if score is not None else ""
    st.markdown(
        f'<span style="background-color:{color};color:white;padding:4px 12px;'
        f'border-radius:12px;font-weight:600;font-size:0.9rem;">'
        f"Confidence: {tier}{score_txt}</span>",
        unsafe_allow_html=True,
    )
    if warning:
        st.warning(warning)
    if breakdown:
        with st.expander("How this score was computed"):
            c1, c2, c3 = st.columns(3)
            c1.metric("Data completeness", f"{breakdown.get('data_completeness', 0)}/40")
            c2.metric("Signal coherence", f"{breakdown.get('signal_coherence', 0)}/35")
            c3.metric("Evidence depth", f"{breakdown.get('evidence_depth', 0)}/25")
            st.caption(
                f"Technical bias: {breakdown.get('technical_bias', '—')} "
                f"({breakdown.get('signals_bull', 0)} bullish / "
                f"{breakdown.get('signals_bear', 0)} bearish signals) · "
                f"{breakdown.get('news_articles', 0)} news articles · "
                f"{breakdown.get('sec_chunks', 0)} SEC chunks"
            )