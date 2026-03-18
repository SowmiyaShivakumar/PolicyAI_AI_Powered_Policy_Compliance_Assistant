"""
Agent 1 — Policy Retrieval Agent

Two parallel retrieval paths:
  Path 1 — Milvus (semantic + keyword)
  Path 2 — Neo4j (intent-based graph traversal with category scoring)

Neo4j traversal uses LLM-identified NIST functions AND categories.
Category scoring ensures the most relevant subcategories rank first.
"""

import concurrent.futures
from typing import Dict, List

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from config import OPENAI_API_KEY, MILVUS_HOST, MILVUS_PORT, COLLECTION_NAME
from retrieval.vector_search import vector_search
from retrieval.bm25_search import bm25_search
from graph.neo4j_connection import Neo4jConnection
from graph.graph_query import get_graph_context
from retrieval.reranker import rerank, build_authority_map

from pymilvus import Collection, connections
from openai import OpenAI

openai_client = OpenAI(api_key=OPENAI_API_KEY)
llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o", temperature=0)


# ══════════════════════════════════════════════════════════════
# LLM Step 1a — Extract keywords for BM25
# ══════════════════════════════════════════════════════════════

KEYWORD_PROMPT = PromptTemplate(
    input_variables=["query"],
    template="""
Extract 3 to 5 NIST cybersecurity domain keywords from this question.
Output only nouns/verbs relevant to cybersecurity policy.
One line, space separated. No explanations.

Question: "{query}"
Keywords:"""
)

def _extract_keywords(query: str) -> str:
    chain    = KEYWORD_PROMPT | llm
    response = chain.invoke({"query": query})
    keywords = response.content.strip()
    print(f"[Retrieval] Keywords: {keywords}")
    return keywords


# ══════════════════════════════════════════════════════════════
# LLM Step 1b — Identify NIST intent for Neo4j
# ══════════════════════════════════════════════════════════════

INTENT_PROMPT = PromptTemplate(
    input_variables=["query"],
    template="""
You are a NIST CSF expert. Identify the NIST CSF functions AND the most
relevant categories for this employee query.

Query: "{query}"

NIST CSF 2.0 structure:
GOVERN   : Organizational Context | Risk Management Strategy |
           Roles and Responsibilities | Policy | Oversight | Supply Chain Risk
IDENTIFY : Asset Management | Risk Assessment | Improvement
PROTECT  : Identity and Access Control | Awareness and Training |
           Data Security | Platform Security | Infrastructure Resilience
DETECT   : Adverse Event Analysis | Continuous Monitoring
RESPOND  : Incident Management | Incident Communication |
           Incident Analysis | Incident Mitigation
RECOVER  : Recovery Plan Execution | Recovery Communication

Mapping rules — use these EXACTLY:
- Remote work / VPN / working abroad / travel / mobile device
  → PROTECT: Infrastructure Resilience, Identity and Access Control
- Lost/stolen device or data breach
  → RESPOND: Incident Mitigation, Incident Communication
- Should I report something / adverse event
  → DETECT: Adverse Event Analysis
- Share data / send data / data protection
  → PROTECT: Data Security, Identity and Access Control
- Who is responsible / governance / roles
  → GOVERN: Roles and Responsibilities
- Asset or hardware inventory
  → IDENTIFY: Asset Management
- Password / authentication / login
  → PROTECT: Identity and Access Control
- Training / awareness / HR / onboarding
  → PROTECT: Awareness and Training
- Supply chain / vendor / third party
  → GOVERN: Supply Chain Risk Management
- Risk management / risk objectives
  → GOVERN: Risk Management Strategy

Return ONLY this JSON:
{{
  "functions": ["function names"],
  "categories": ["category names ordered by relevance — most relevant first"]
}}
"""
)

def _identify_intent(query: str) -> Dict:
    import json
    chain    = INTENT_PROMPT | llm
    response = chain.invoke({"query": query})
    raw      = response.content.strip().replace("```json","").replace("```","").strip()
    try:
        intent = json.loads(raw)
        print(f"[Retrieval] Intent: {intent}")
        return intent
    except Exception:
        print(f"[Retrieval] Intent parse failed: {raw}")
        return {"functions": [], "categories": []}


# ══════════════════════════════════════════════════════════════
# Path 1 — Milvus hybrid search
# ══════════════════════════════════════════════════════════════

def _milvus_search(query: str, keywords: str, top_k: int,
                   intent: Dict = None) -> List[Dict]:
    """
    Metadata filtering strategy:
      - LLM identified exactly ONE function → filter Milvus by that function
        e.g. "I lost a laptop" → RESPOND only → ignores GOVERN/IDENTIFY noise
      - Multiple functions identified → no filter (too broad)
      - category not filtered here — too granular, reduces recall
        Neo4j handles category precision via graph traversal
    """
    from config import EMBEDDING_MODEL

    # LLM-driven metadata filter
    nist_function_filter = None
    if intent:
        functions = intent.get("functions", [])
        if len(functions) == 1:
            nist_function_filter = functions[0]
            print(f"[Retrieval - Milvus] Metadata filter: nist_function={nist_function_filter}")
        else:
            print(f"[Retrieval - Milvus] No filter — multiple functions: {functions}")

    resp      = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    embedding = resp.data[0].embedding

    vector_hits = vector_search(embedding, top_k=top_k,
                                nist_function=nist_function_filter)
    bm25_hits   = bm25_search(keywords, top_k=top_k,
                              nist_function=nist_function_filter)

    # Normalise vector scores to 0-1
    if vector_hits:
        max_v = max(h["score"] for h in vector_hits)
        min_v = min(h["score"] for h in vector_hits)
        rng   = max_v - min_v if max_v != min_v else 1.0
        for h in vector_hits:
            h["score"] = round((h["score"] - min_v) / rng, 4)

    merged = {}
    for h in vector_hits:
        merged[h["subcategory_id"]] = {
            **h, "vector_score": h["score"], "bm25_score": 0.0, "source": "vector"
        }
    for h in bm25_hits:
        sid = h["subcategory_id"]
        if sid in merged:
            merged[sid]["bm25_score"] = h["score"]
            merged[sid]["source"]     = "hybrid"
        else:
            merged[sid] = {
                **h, "vector_score": 0.0,
                "bm25_score": h["score"], "source": "bm25"
            }
    for item in merged.values():
        item["score"] = round(
            0.7 * item["vector_score"] + 0.3 * item["bm25_score"], 4
        )

    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    print(f"[Retrieval - Milvus] {[r['subcategory_id'] for r in results]}")
    return results


# ══════════════════════════════════════════════════════════════
# Path 2 — Neo4j intent-based graph traversal
# ══════════════════════════════════════════════════════════════

def _neo4j_intent_search(intent: Dict, top_k: int) -> List[Dict]:
    """
    Traverse Neo4j using identified functions + categories.
    Categories are ordered by relevance — position used for scoring.
    e.g. Incident Mitigation at index 0 → score 1.0
         Incident Communication at index 1 → score 0.85
         Incident Analysis at index 2 → score 0.70

    This ensures RS.MI-01 (Incident Mitigation) beats RS.AN-07 (Incident Analysis).
    """
    functions  = intent.get("functions", [])
    categories = intent.get("categories", [])

    if not functions and not categories:
        return []

    try:
        conn = Neo4jConnection()

        # Build category priority map from ordered list
        # categories[0] = most relevant → score 1.0
        # categories[1] → score 0.85
        # categories[2] → score 0.70 etc.
        category_scores = {}
        for i, cat in enumerate(categories):
            category_scores[cat] = round(1.0 - (i * 0.15), 2)

        data = conn.run("""
            MATCH (f:NistFunction)-[:HAS_CATEGORY]->(c:Category)
                  -[:HAS_SUBCATEGORY]->(s:Subcategory)
            WHERE f.name IN $functions OR c.name IN $categories
            RETURN s.id          AS subcategory_id,
                   s.description AS description,
                   c.name        AS category,
                   f.name        AS nist_function
            LIMIT 20
        """, {"functions": functions, "categories": categories})

        conn.close()

        if not data:
            return []

        # Score each result using category priority
        scored = []
        for r in data:
            cat   = r["category"]
            fn    = r["nist_function"]
            score = category_scores.get(cat, 0.3)

            # Boost if function also matches (not just category)
            if fn in functions:
                score = min(1.0, score + 0.1)

            scored.append({
                "subcategory_id": r["subcategory_id"],
                "description":    r["description"],
                "category":       cat,
                "nist_function":  fn,
                "score":          score,
            })

        # Sort by score, take top_k
        scored = sorted(scored, key=lambda x: x["score"], reverse=True)[:top_k]

        # Fetch text from Milvus for these subcategories
        connections.connect(host=MILVUS_HOST, port=MILVUS_PORT)
        col = Collection(COLLECTION_NAME)
        col.load()

        chunks = []
        for r in scored:
            text = r["description"]
            try:
                result = col.query(
                    expr=f'subcategory_id == "{r["subcategory_id"]}"',
                    output_fields=["text"],
                    limit=1,
                )
                if result:
                    text = result[0]["text"]
            except Exception:
                pass

            chunks.append({
                "subcategory_id": r["subcategory_id"],
                "text":           text,
                "nist_function":  r["nist_function"],
                "category":       r["category"],
                "score":          r["score"],
                "source":         "neo4j",
            })

        print(f"[Retrieval - Neo4j] {[c['subcategory_id'] for c in chunks]}")
        return chunks

    except Exception as e:
        print(f"[Retrieval - Neo4j] Failed: {e}")
        return []


# ══════════════════════════════════════════════════════════════
# Merge both paths
# ══════════════════════════════════════════════════════════════

def _merge(milvus_chunks: List[Dict],
           neo4j_chunks:  List[Dict],
           top_k: int) -> List[Dict]:
    """
    Merge results. Found in BOTH = highest confidence = boosted.
    """
    merged = {}

    for c in milvus_chunks:
        sid = c["subcategory_id"]
        merged[sid] = {**c, "milvus_score": c["score"], "neo4j_score": 0.0}

    for c in neo4j_chunks:
        sid = c["subcategory_id"]
        if sid in merged:
            merged[sid]["neo4j_score"] = c["score"]
            merged[sid]["score"]       = round(
                merged[sid]["milvus_score"] * 0.5 +
                c["score"] * 0.5, 4
            )
            merged[sid]["source"] = "milvus+neo4j"
        else:
            merged[sid] = {
                **c, "milvus_score": 0.0,
                "neo4j_score": c["score"]
            }

    results = sorted(merged.values(), key=lambda x: x["score"], reverse=True)[:top_k]

    print(f"\n[Retrieval] Final merged:")
    for r in results:
        print(f"  {r['subcategory_id']:12} "
              f"score={r['score']:.3f}  source={r['source']}")

    return results


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def run(query: str, top_k: int = 5) -> Dict:
    print(f"\n[Agent 1 - Retrieval] Query: {query}")

    # Step 1 — LLM extracts keywords + identifies intent (parallel)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        kw_future     = ex.submit(_extract_keywords, query)
        intent_future = ex.submit(_identify_intent, query)
        keywords = kw_future.result()
        intent   = intent_future.result()

    # Step 2 — Milvus + Neo4j in parallel
    # Intent passed to Milvus for LLM-driven metadata filtering
    print("[Agent 1 - Retrieval] Running Milvus + Neo4j in parallel...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        milvus_future = ex.submit(_milvus_search, query, keywords, top_k, intent)
        neo4j_future  = ex.submit(_neo4j_intent_search, intent, top_k)
        milvus_chunks = milvus_future.result()
        neo4j_chunks  = neo4j_future.result()

    # Step 3 — merge
    chunks = _merge(milvus_chunks, neo4j_chunks, top_k)

    # Step 4 — graph context for all final chunks
    all_ids       = [c["subcategory_id"] for c in chunks]
    graph_context = get_graph_context(all_ids)
    build_authority_map(graph_context)
    # Step 5 — re-rank using authority + phase relevance
    # Derive query type hint from LLM intent functions
    # (exact query_type comes from Agent 2 later, this is a best-guess)
    functions = intent.get("functions", [])
    if "RESPOND" in functions or "RECOVER" in functions:
        query_type_hint = "INCIDENT"
    elif set(functions) <= {"GOVERN", "IDENTIFY"}:
        query_type_hint = "INFO"
    else:
        query_type_hint = "ACTION"

    chunks = rerank(chunks, query_type_hint, graph_context)

    print(f"\n[Agent 1 - Retrieval] Graph context:")
    for sid, data in graph_context.items():
        print(f"  [{sid}] {data.get('category','')} "
              f"| policies: {data.get('policies',[])[:2]}")

    print(f"\n[Agent 1 - Retrieval] Final chunks after re-ranking: "
          f"{[c['subcategory_id'] for c in chunks]}")

    return {
        "query":         query,
        "keywords":      keywords,
        "intent":        intent,
        "chunks":        chunks,
        "graph_context": graph_context,
    }