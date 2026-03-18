"""
Re-ranker — Weighted Score Fusion

Algorithm: Linear Score Combination
  final_score = merge_score    × 0.5
              + authority_score × 0.3
              + phase_score     × 0.2

NO hardcoded policy lists or subcategory prefixes.

Authority → derived from how many subcategories reference a policy
            (more references in the PDF = more authoritative)
            Built once from actual chunk data at startup.

Phase     → derived from nist_function field already stored in
            every chunk from Milvus ingestion.
            INCIDENT → RESPOND/DETECT chunks score high
            ACTION   → PROTECT/GOVERN chunks score high
            INFO     → GOVERN/IDENTIFY chunks score high
"""

from typing import List, Dict


# ══════════════════════════════════════════════════════════════
# BUILD AUTHORITY MAP FROM ACTUAL PDF DATA
# Called once at startup — reads from Milvus chunks
# ══════════════════════════════════════════════════════════════

_authority_map: Dict[str, float] = {}   # policy_name → score 0-1


def build_authority_map(graph_context: Dict) -> None:
    from collections import Counter

    global _authority_map
    policy_counts = Counter()

    for sid, data in graph_context.items():
        for p in data.get("policies", []):
            policy_counts[p] += 1

    if not policy_counts:
        return

    max_count = max(policy_counts.values())

    _authority_map = {
        policy: round(count / max_count, 4)
        for policy, count in policy_counts.items()
    }

    print(f"[Re-ranker] Authority map built: {len(_authority_map)} policies")

def _get_authority_score(policies: List[str]) -> float:
    """
    Return the highest authority score among the chunk's policies.
    Falls back to 0.3 if policy not seen in training data.
    """
    if not policies or not _authority_map:
        return 0.3

    scores = [_authority_map.get(p, 0.3) for p in policies]
    return max(scores)


# ══════════════════════════════════════════════════════════════
# PHASE RELEVANCE — from nist_function, not hardcoded prefixes
# ══════════════════════════════════════════════════════════════

# Maps query_type → which NIST functions are most relevant
# These are the 6 NIST functions — not subcategory prefixes
PHASE_FUNCTION_MAP = {
    "INCIDENT": {
        "high":   ["RESPOND", "DETECT"],
        "medium": ["RECOVER"],
        "low":    ["GOVERN", "IDENTIFY", "PROTECT"],
    },
    "ACTION": {
        "high":   ["PROTECT", "GOVERN"],
        "medium": ["IDENTIFY"],
        "low":    ["RESPOND", "RECOVER"],
    },
    "INFO": {
        "high":   ["GOVERN", "IDENTIFY"],
        "medium": ["PROTECT"],
        "low":    ["RESPOND", "RECOVER"],
    },
}


def _get_phase_score(nist_function: str, query_type: str) -> float:
    """
    Score based on whether the chunk's NIST function matches
    what this query type needs.
    nist_function is already stored in every chunk from Milvus.
    """
    phases = PHASE_FUNCTION_MAP.get(query_type, PHASE_FUNCTION_MAP["ACTION"])

    if nist_function in phases["high"]:
        return 1.0
    if nist_function in phases["medium"]:
        return 0.6
    if nist_function in phases["low"]:
        return 0.2

    return 0.4   # unknown function → neutral


# ══════════════════════════════════════════════════════════════
# MAIN RERANK FUNCTION
# ══════════════════════════════════════════════════════════════

def rerank(
    chunks:        List[Dict],
    query_type:    str,
    graph_context: Dict,
) -> List[Dict]:
    """
    Re-rank chunks using Weighted Score Fusion.

    Inputs:
      chunks        → merged results from Milvus + Neo4j
      query_type    → INCIDENT / ACTION / INFO
      graph_context → policies attached to each chunk (from Neo4j)

    Output:
      same chunks reordered by final_score
      original merge_score preserved inside each chunk
    """
    print(f"\n[Re-ranker] Re-ranking {len(chunks)} chunks | type={query_type}")

    for chunk in chunks:
        sid           = chunk["subcategory_id"]
        nist_function = chunk.get("nist_function", "")

        # Policies for this chunk from graph context
        policies = graph_context.get(sid, {}).get("policies", [])

        # Three signals
        authority = _get_authority_score(policies)
        phase     = _get_phase_score(nist_function, query_type)
        merge     = chunk.get("score", 0.5)

        # Weighted combination
        final = round(
            merge     * 0.5 +
            authority * 0.3 +
            phase     * 0.2,
            4
        )

        # Preserve original, add new scores
        chunk["merge_score"]     = merge
        chunk["authority_score"] = authority
        chunk["phase_score"]     = phase
        chunk["score"]           = final

    reranked = sorted(chunks, key=lambda x: x["score"], reverse=True)

    print(f"[Re-ranker] Results:")
    for r in reranked:
        print(f"  {r['subcategory_id']:12} "
              f"final={r['score']:.3f}  "
              f"merge={r.get('merge_score',0):.3f}  "
              f"authority={r['authority_score']:.2f}  "
              f"phase={r['phase_score']:.2f}  "
              f"fn={r.get('nist_function','')}")

    return reranked