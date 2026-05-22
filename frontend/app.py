import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests
import streamlit as st

from frontend.components.confidence_badge import render_confidence_badge
from frontend.components.report_view import render_report_with_citations
from frontend.components.validator_panel import render_validator_panel

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _post(path: str, payload: dict, timeout: int = 180) -> dict:
    try:
        resp = requests.post(f"{BACKEND_URL}{path}", json=payload, timeout=timeout)
        return resp.json()
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Could not reach backend at {BACKEND_URL}: {e}",
        }


def _render_analyze(result: dict) -> None:
    status = result.get("status")

    if status == "success":
        data = result["data"]
        render_confidence_badge(
            data.get("confidence_tier", "Unknown"),
            data.get("confidence_score"),
            data.get("confidence_warning"),
            data.get("confidence_breakdown"),
        )
        st.caption(
            f"{data['ticker']} · {data['window']} · generated {data['generated_at']}"
        )
        render_report_with_citations(data["report_text"], data.get("evidence", []))
    elif status == "blocked":
        render_confidence_badge(
            result.get("confidence_tier", "Very Low"),
            result.get("confidence_score"),
        )
        st.error(result.get("error", "Report blocked."))
    else:
        st.error(result.get("error", "Analysis failed."))


st.set_page_config(page_title="Stock Analysis System", layout="wide")
st.title("Stock Analysis System")
st.caption("Evidence-based US equity research. Not trading advice.")

tab_report, tab_validate = st.tabs(["Stock Report", "View Validator"])

with tab_report:
    with st.form("analyze_form"):
        c1, c2 = st.columns([2, 1])
        ticker = c1.text_input("Ticker", placeholder="NVDA").strip().upper()
        window = c2.selectbox("Window", ["7d", "30d", "90d"])
        company = st.text_input(
            "Company name (optional)", placeholder="NVIDIA Corporation"
        ).strip()
        submitted = st.form_submit_button("Analyze")

    if submitted:
        if not ticker:
            st.warning("Enter a ticker symbol.")
        else:
            payload = {"ticker": ticker, "window": window}
            if company:
                payload["company_name"] = company
            with st.spinner(
                f"Analyzing {ticker}... a ticker's first analysis can take a few "
                "minutes while its SEC filings are downloaded and indexed."
            ):
                result = _post("/analyze", payload, timeout=600)
            _render_analyze(result)

with tab_validate:
    render_validator_panel(
        lambda thesis, tk, tf: _post(
            "/validate-view", {"thesis": thesis, "ticker": tk, "timeframe": tf}
        )
    )