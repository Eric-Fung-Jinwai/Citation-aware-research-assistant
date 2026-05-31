import re

import streamlit as st


def parse_citations(text: str, citation_map: dict) -> tuple[str, list]:
    footnotes = []
    seen = {}
    counter = 1

    def replacer(match):
        nonlocal counter
        n = int(match.group(1))
        if n not in seen:
            seen[n] = counter
            footnotes.append(citation_map.get(n))
            counter += 1
        return f"[{seen[n]}]"

    clean_text = re.sub(r'\[cite:(\d+)]', replacer, text)
    return clean_text, footnotes


def render_report_with_citations(report_text: str, evidence: list[dict]) -> None:
    """Render report markdown with [cite:N] tags resolved to numbered footnotes."""
    citation_map = {block["citation_index"]: block.get("citation") for block in evidence}
    clean_text, footnotes = parse_citations(report_text, citation_map)

    st.markdown(clean_text)

    if not footnotes:
        return

    st.divider()
    st.markdown("**Sources**")
    for i, fn in enumerate(footnotes, start=1):
        if fn and fn.get("url"):
            st.markdown(f"{i}. [{fn['source_name']}]({fn['url']}) — {fn.get('date', '')}")
        elif fn:
            st.markdown(f"{i}. {fn['source_name']} — {fn.get('date', '')}")
        else:
            st.markdown(f"{i}. Source unavailable")