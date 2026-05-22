import os
import threading
from pathlib import Path
from typing import Optional

import chromadb
from chromadb import Collection, PersistentClient
from chromadb.config import Settings

_DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "chromadb"
_COLLECTION_NAME = "sec_filings"
_MAX_TOP_K = 50

_client: Optional[PersistentClient] = None
_collection: Optional[Collection] = None
_init_lock = threading.Lock()


def _get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is not None:
        return _collection
    with _init_lock:
        if _collection is not None:
            return _collection
        db_path = Path(os.getenv("CHROMADB_PATH", str(_DEFAULT_DB_PATH)))
        db_path.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert_chunks(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict],
) -> None:
    lengths = {len(ids), len(embeddings), len(documents), len(metadatas)}
    if len(lengths) != 1:
        raise ValueError(
            f"upsert_chunks: ids/embeddings/documents/metadatas must have equal length; "
            f"got {len(ids)}/{len(embeddings)}/{len(documents)}/{len(metadatas)}"
        )
    col = _get_collection()
    col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)


def query_chunks(
    query_embedding: list[float],
    ticker: str,
    top_k: int = 5,
):
    if top_k <= 0:
        raise ValueError(f"top_k must be > 0, got {top_k}")
    top_k = min(top_k, _MAX_TOP_K)
    col = _get_collection()
    return col.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where={"ticker": ticker.strip().upper()},
        include=["documents", "metadatas", "distances"],
    )


def ticker_chunk_count(ticker: str) -> int:
    col = _get_collection()
    # limit=1 avoids fetching all IDs just to answer "any exist?"
    result = col.get(where={"ticker": ticker.strip().upper()}, include=[], limit=1)
    return len(result["ids"])