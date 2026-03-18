from typing import List, Dict
from graph.neo4j_connection import Neo4jConnection


def build_graph(chunks: List[Dict]):
    """
    Build the policy graph in Neo4j from the same chunks
    used for Milvus ingestion.

    Graph schema:
        (:NistFunction)-[:HAS_CATEGORY]->(:Category)
        (:Category)-[:HAS_SUBCATEGORY]->(:Subcategory)
        (:Subcategory)-[:REFERENCES_POLICY]->(:Policy)

    Each chunk = one Subcategory node.
    Policies are extracted from the pipe-separated 'policies' field.
    """
    conn = Neo4jConnection()
    if not conn.verify():
        raise ConnectionError("Cannot connect to Neo4j. Is it running?")

    print("[graph] Creating constraints and indexes...")
    _create_constraints(conn)

    print(f"[graph] Building graph from {len(chunks)} chunks...")
    for chunk in chunks:
        _create_nodes(conn, chunk)

    # Count what was created
    summary = conn.run("""
        MATCH (f:NistFunction) WITH count(f) as functions
        MATCH (c:Category)     WITH functions, count(c) as categories
        MATCH (s:Subcategory)  WITH functions, categories, count(s) as subcategories
        MATCH (p:Policy)       WITH functions, categories, subcategories, count(p) as policies
        RETURN functions, categories, subcategories, policies
    """)
    if summary:
        s = summary[0]
        print(f"[graph] Created:")
        print(f"         NistFunction nodes : {s['functions']}")
        print(f"         Category nodes     : {s['categories']}")
        print(f"         Subcategory nodes  : {s['subcategories']}")
        print(f"         Policy nodes       : {s['policies']}")

    conn.close()
    print("[graph] Graph build complete.")


# ── Internal helpers ──────────────────────────────────────────────────────────
def _create_constraints(conn: Neo4jConnection):
    """Unique constraints — prevent duplicate nodes on re-run."""
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (f:NistFunction) REQUIRE f.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category)     REQUIRE c.code IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Subcategory)  REQUIRE s.id   IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Policy)       REQUIRE p.name IS UNIQUE",
    ]
    for c in constraints:
        conn.run(c)


def _create_nodes(conn: Neo4jConnection, chunk: Dict):
    """
    For one chunk, create/merge all nodes and relationships.

    chunk fields used:
        subcategory_id  → Subcategory.id
        description     → Subcategory.description
        nist_function   → NistFunction.name
        category        → Category.name
        policies        → pipe-separated Policy names
    """
    subcat_id    = chunk.get("subcategory_id") or chunk.get("title", "")
    description  = chunk.get("description", subcat_id)
    nist_fn      = chunk.get("nist_function", "GENERAL")
    category     = chunk.get("category", "General")
    policies_str = chunk.get("policies", "")

    # Derive category code from subcategory_id e.g. "GV.OC" from "GV.OC-01"
    try:
        cat_code = ".".join(subcat_id.split("-")[0].split(".")[:2])  # "GV.OC"
    except Exception:
        cat_code = category

    # ── 1. NistFunction node ──────────────────────────────────────────────────
    conn.run(
        "MERGE (f:NistFunction {name: $name})",
        {"name": nist_fn}
    )

    # ── 2. Category node + link to NistFunction ───────────────────────────────
    conn.run("""
        MERGE (c:Category {code: $code})
        SET c.name = $name
        WITH c
        MATCH (f:NistFunction {name: $nist_fn})
        MERGE (f)-[:HAS_CATEGORY]->(c)
    """, {
        "code":    cat_code,
        "name":    category,
        "nist_fn": nist_fn,
    })

    # ── 3. Subcategory node + link to Category ────────────────────────────────
    conn.run("""
        MERGE (s:Subcategory {id: $id})
        SET s.description  = $description,
            s.nist_function = $nist_fn,
            s.category_code = $cat_code
        WITH s
        MATCH (c:Category {code: $cat_code})
        MERGE (c)-[:HAS_SUBCATEGORY]->(s)
    """, {
        "id":          subcat_id,
        "description": description,
        "nist_fn":     nist_fn,
        "cat_code":    cat_code,
    })

    # ── 4. Policy nodes + link to Subcategory ────────────────────────────────
    if policies_str:
        policy_names = [p.strip() for p in policies_str.split("|") if p.strip()]
        for policy_name in policy_names:
            conn.run("""
                MERGE (p:Policy {name: $name})
                WITH p
                MATCH (s:Subcategory {id: $subcat_id})
                MERGE (s)-[:REFERENCES_POLICY]->(p)
            """, {
                "name":      policy_name,
                "subcat_id": subcat_id,
            })