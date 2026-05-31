"""
finance-rag skill

Given a ticker and a natural-language query, fetches (and indexes if needed)
SEC filings, then returns the top-k most relevant chunks as EvidenceBlock[]
wrapped in a SkillResult envelope.
"""

import hashlib

from sentence_transformers import SentenceTransformer

from backend.models.citation import SkillResult
from backend.models.report import EvidenceBlock, EvidenceCitation
from backend.utils.cache import get_cached, set_cached
from backend.utils.sec_fetcher import fetch_and_index
from backend.utils.vector_store import query_chunks, ticker_chunk_count

_embedder: SentenceTransformer | None = None


def _get_embedder() -> SentenceTransformer:
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedder


async def query_sec_filings(
    ticker: str,
    query: str,
    top_k: int = 5,
    citation_index_start: int = 0,
) -> dict:
    """
    Returns a SkillResult whose data contains:
      { "blocks": [EvidenceBlock.model_dump(), ...] }
    """
    ticker = ticker.upper()
    query_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    cached = await get_cached(f"rag:{ticker}:{query_hash}:{top_k}")
    if cached is not None:
        return cached

    # Index filings if not yet in the vector store
    if ticker_chunk_count(ticker) == 0:
        index_result = fetch_and_index(ticker)
        if index_result["status"] == "failed":
            return SkillResult(
                status="degraded",
                error=f"SEC filing index failed: {index_result.get('error')}",
                source="finance-rag",
            ).model_dump()

    if ticker_chunk_count(ticker) == 0:
        return SkillResult(
            status="degraded",
            error=f"No SEC filings found for {ticker}",
            source="finance-rag",
        ).model_dump()

    try:
        embedder = _get_embedder()
        query_vec = embedder.encode([query], show_progress_bar=False)[0].tolist()
        results = query_chunks(query_embedding=query_vec, ticker=ticker, top_k=top_k)
    except Exception as e:
        return SkillResult(
            status="degraded",
            error=f"Vector store query failed: {e}",
            source="finance-rag",
        ).model_dump()

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]

    if not docs:
        return SkillResult(
            status="degraded",
            error="No relevant SEC filing chunks returned",
            source="finance-rag",
        ).model_dump()

    blocks: list[EvidenceBlock] = []
    for i, (doc, meta) in enumerate(zip(docs, metas)):
        blocks.append(
            EvidenceBlock(
                citation_index=citation_index_start + i,
                source_type="sec_filing",
                content=doc,
                citation=EvidenceCitation(
                    source_name=f"SEC {meta.get('form_type', 'Filing')} — {ticker}",
                    url=meta.get("url"),
                    date=meta.get("date", ""),
                ),
            )
        )

    result = SkillResult(
        status="success",
        data={"blocks": [b.model_dump() for b in blocks]},
        source="finance-rag",
    ).model_dump()
    await set_cached(f"rag:{ticker}:{query_hash}:{top_k}", result, ttl_seconds=86400)
    return result