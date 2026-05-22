"""
Downloads recent SEC filings from EDGAR and embeds them into ChromaDB.

Flow:
  fetch_and_index(ticker)
    → resolve ticker → CIK via EDGAR browse API, then fetch filings list from submissions JSON
    → download filing text
    → chunk into 500-800 token blocks
    → embed with sentence-transformers
    → upsert into ChromaDB via vector_store
"""

import hashlib
import re
import time

import requests
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer

from backend.utils.vector_store import ticker_chunk_count, upsert_chunks

_EDGAR_FILING_BASE = "https://www.sec.gov/Archives/edgar/data"
_FORM_TYPES = ["10-K", "10-Q", "8-K"]
_MAX_FILINGS_PER_TYPE = 3
_REQUEST_PAUSE = 0.12  # EDGAR rate-limit: ~10 req/s

_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=80)
_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


def _edgar_headers() -> dict:
    return {"User-Agent": "StockAnalysisSystem contact@example.com"}


def _get_cik(ticker: str) -> str | None:
    url = "https://www.sec.gov/cgi-bin/browse-edgar"
    params = {"company": "", "CIK": ticker, "type": "", "dateb": "", "owner": "include",
               "count": "1", "search_text": "", "action": "getcompany", "output": "atom"}
    try:
        r = requests.get(url, params=params, headers=_edgar_headers(), timeout=10)
        r.raise_for_status()
        # CIK appears in the atom feed as /cgi-bin/browse-edgar?action=getcompany&CIK=XXXXXXXXXX
        match = re.search(r"CIK=(\d+)", r.text)
        return match.group(1).lstrip("0") if match else None
    except Exception:
        return None


def _get_recent_filings(cik: str, form_type: str) -> list[dict]:
    url = f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"
    try:
        r = requests.get(url, headers=_edgar_headers(), timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return []

    filings = data.get("filings", {}).get("recent", {})
    forms = filings.get("form", [])
    dates = filings.get("filingDate", [])
    accessions = filings.get("accessionNumber", [])
    primary_docs = filings.get("primaryDocument", [])

    results = []
    for form, date, acc, doc in zip(forms, dates, accessions, primary_docs):
        if form == form_type:
            acc_clean = acc.replace("-", "")
            filing_url = f"{_EDGAR_FILING_BASE}/{cik}/{acc_clean}/{doc}"
            results.append({"form_type": form, "date": date, "url": filing_url, "accession": acc})
            if len(results) >= _MAX_FILINGS_PER_TYPE:
                break
    return results


def _download_text(url: str) -> str:
    try:
        time.sleep(_REQUEST_PAUSE)
        r = requests.get(url, headers=_edgar_headers(), timeout=20)
        r.raise_for_status()
        text = r.text
        # Strip HTML tags if present
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s{3,}", "\n\n", text)
        return text[:500_000]  # cap at 500 k chars to bound memory
    except Exception:
        return ""


def _chunk_id(ticker: str, form_type: str, accession: str, chunk_idx: int) -> str:
    key = f"{ticker}|{form_type}|{accession}|{chunk_idx}"
    return hashlib.sha1(key.encode()).hexdigest()


def fetch_and_index(ticker: str, force: bool = False) -> dict:
    """
    Download and embed SEC filings for ticker into ChromaDB.
    Skips if already indexed (unless force=True).
    Returns { status, chunks_added, filings_processed }.
    """
    ticker = ticker.upper()

    if not force and ticker_chunk_count(ticker) > 0:
        return {"status": "skipped", "chunks_added": 0, "filings_processed": 0}

    cik = _get_cik(ticker)
    if not cik:
        return {"status": "failed", "error": f"CIK not found for {ticker}", "chunks_added": 0}

    embedder = _get_embedder()
    total_chunks = 0
    total_filings = 0

    for form_type in _FORM_TYPES:
        filings = _get_recent_filings(cik, form_type)
        for filing in filings:
            text = _download_text(filing["url"])
            if not text.strip():
                continue

            chunks = _splitter.split_text(text)
            if not chunks:
                continue

            embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()
            ids = [_chunk_id(ticker, form_type, filing["accession"], i) for i in range(len(chunks))]
            metadatas = [
                {
                    "ticker": ticker,
                    "form_type": filing["form_type"],
                    "date": filing["date"],
                    "url": filing["url"],
                    "chunk_index": i,
                }
                for i in range(len(chunks))
            ]

            upsert_chunks(ids=ids, embeddings=embeddings, documents=chunks, metadatas=metadatas)
            total_chunks += len(chunks)
            total_filings += 1

    return {"status": "success", "chunks_added": total_chunks, "filings_processed": total_filings}