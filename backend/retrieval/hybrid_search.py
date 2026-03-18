from typing import List, Dict, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, EMBEDDING_MODEL
from retrieval.vector_search import vector_search
from retrieval.bm25_search   import bm25_search

client = OpenAI(api_key=OPENAI_API_KEY)

VECTOR_WEIGHT = 0.7
BM25_WEIGHT   = 0.3


def _embed_query(query: str) -> List[float]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    return response.data[0].embedding


def _normalise(hits: List[Dict]) -> List[Dict]:
    """Normalise scores to 0-1 range."""
    if not hits:
        return hits
    max_score = max(h["score"] for h in hits)
    min_score = min(h["score"] for h in hits)
    rng = max_score - min_score if max_score != min_score else 1.0
    for h in hits:
        h["score"] = round((h["score"] - min_score) / rng, 4)
    return hits


def hybrid_search(
    query: str,
    top_k: int = 5,
    nist_function: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict]:
    """
    Combine vector + BM25 results.
    Both scores normalised to 0-1 before combining.
    """
    # Step 1 — vector search
    query_embedding = _embed_query(query)
    vector_results  = _normalise(
        vector_search(query_embedding, top_k=top_k,
                      nist_function=nist_function, category=category)
    )

    # Step 2 — BM25 search
    bm25_results = _normalise(
        bm25_search(query, top_k=top_k,
                    nist_function=nist_function, category=category)
    )

    # Step 3 — merge by subcategory_id
    merged = {}

    for hit in vector_results:
        sid = hit["subcategory_id"]
        merged[sid] = {
            **hit,
            "vector_score": hit["score"],
            "bm25_score":   0.0,
            "source":       "vector",
        }

    for hit in bm25_results:
        sid = hit["subcategory_id"]
        if sid in merged:
            merged[sid]["bm25_score"] = hit["score"]
            merged[sid]["source"]     = "hybrid"
        else:
            merged[sid] = {
                **hit,
                "vector_score": 0.0,
                "bm25_score":   hit["score"],
                "source":       "bm25",
            }

    # Step 4 — weighted combined score
    for sid, item in merged.items():
        item["score"] = round(
            VECTOR_WEIGHT * item["vector_score"] +
            BM25_WEIGHT   * item["bm25_score"],
            4,
        )

    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)

    # Show what we got
    print("\n[hybrid] Final ranked results:")
    for r in results[:top_k]:
        print(f"  {r['subcategory_id']}  score={r['score']}  source={r['source']}")

    return results[:top_k]