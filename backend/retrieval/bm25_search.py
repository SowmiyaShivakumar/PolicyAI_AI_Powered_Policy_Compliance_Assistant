import json
import os
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi
from pymilvus import Collection, connections
from config import MILVUS_HOST, MILVUS_PORT, COLLECTION_NAME

# In-memory BM25 index — built once, reused across queries
_bm25_index = None
_bm25_chunks = []   # stores the full chunk dicts matching BM25 positions


def _build_index():
    """
    Pull all chunks from Milvus and build BM25 index in memory.
    Called once on first search — no separate storage needed.
    """
    global _bm25_index, _bm25_chunks

    connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
    col = Collection(COLLECTION_NAME)
    col.load()

    # Fetch all stored chunks (107 records — small enough for in-memory)
    results = col.query(
        expr='subcategory_id != ""',
        output_fields=["subcategory_id", "text", "nist_function", "category"],
        limit=500,
    )

    _bm25_chunks = results

    # Tokenize each chunk text for BM25
    tokenized = [chunk["text"].lower().split() for chunk in _bm25_chunks]
    _bm25_index = BM25Okapi(tokenized)

    print(f"[bm25] Index built with {len(_bm25_chunks)} chunks.")


def bm25_search(
    query: str,
    top_k: int = 5,
    nist_function: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict]:
    """
    Search chunks using BM25 keyword matching.
    Same metadata filtering as vector search.

    Returns list of:
    {
        "subcategory_id": "GV.OC-01",
        "text":           "...",
        "nist_function":  "GOVERN",
        "category":       "Organizational Context",
        "score":          0.73    ← BM25 score normalised 0-1
    }
    """
    global _bm25_index, _bm25_chunks

    # Build index on first call
    if _bm25_index is None:
        _build_index()

    # Score all chunks
    tokenized_query = query.lower().split()
    scores = _bm25_index.get_scores(tokenized_query)

    # Pair each chunk with its score
    scored = [
        (_bm25_chunks[i], float(scores[i]))
        for i in range(len(_bm25_chunks))
    ]

    # Apply metadata filters
    if nist_function:
        scored = [(c, s) for c, s in scored if c["nist_function"] == nist_function]
    if category:
        scored = [(c, s) for c, s in scored if c["category"] == category]

    # Sort by score descending, take top_k
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:top_k]

    # Normalise scores to 0-1 range
    max_score = top[0][1] if top and top[0][1] > 0 else 1.0

    hits = []
    for chunk, score in top:
        if score == 0:
            continue                    # skip zero-score results
        hits.append({
            "subcategory_id": chunk["subcategory_id"],
            "text":           chunk["text"],
            "nist_function":  chunk["nist_function"],
            "category":       chunk["category"],
            "score":          round(score / max_score, 4),
            "source":         "bm25",
        })

    return hits
