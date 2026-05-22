import re


def parse_citations(text: str, citation_map: dict) -> tuple[str, list]:
    """
    Replace [cite:N] tags with sequential display markers.
    Returns (cleaned_text, ordered_footnotes).
    citation_map: {citation_index: EvidenceCitation dict or None}
    Duplicate [cite:N] references collapse to the same footnote number.
    """
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

    clean_text = re.sub(r'\[cite:(\d+)\]', replacer, text)
    return clean_text, footnotes