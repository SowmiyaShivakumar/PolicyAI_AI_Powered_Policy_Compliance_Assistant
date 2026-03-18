from typing import List, Dict, Optional
from pymilvus import Collection, connections, utility
from config import MILVUS_HOST, MILVUS_PORT, COLLECTION_NAME


def connect():
    """Connect only if not already connected."""
    try:
        # Check if already connected
        utility.has_collection(COLLECTION_NAME)
    except Exception:
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)


def vector_search(
    query_embedding: List[float],
    top_k: int = 5,
    nist_function: Optional[str] = None,
    category: Optional[str] = None,
) -> List[Dict]:
    """
    Search Milvus by vector similarity.
    Optionally filter by nist_function or category.
    """
    connect()
    col = Collection(COLLECTION_NAME)
    col.load()

    # Build metadata filter
    filters = []
    if nist_function:
        filters.append(f'nist_function == "{nist_function}"')
    if category:
        filters.append(f'category == "{category}"')
    expr = " and ".join(filters) if filters else None

    try:
        results = col.search(
            data=[query_embedding],
            anns_field="embedding",
            param={"metric_type": "COSINE", "params": {"nprobe": 16}},
            limit=top_k,
            expr=expr,
            output_fields=["subcategory_id", "text", "nist_function", "category"],
        )

        hits = []
        for hit in results[0]:
            hits.append({
                "subcategory_id": hit.entity.get("subcategory_id"),
                "text":           hit.entity.get("text"),
                "nist_function":  hit.entity.get("nist_function"),
                "category":       hit.entity.get("category"),
                "score":          round(hit.score, 4),
                "source":         "vector",
            })

        print(f"[vector] Found {len(hits)} results")
        return hits

    except Exception as e:
        print(f"[vector] Search failed: {e}")
        return []