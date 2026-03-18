from typing import List, Dict
from graph.neo4j_connection import Neo4jConnection


def get_graph_context(subcategory_ids: List[str]) -> Dict:
    """
    Given a list of subcategory IDs from Milvus search results,
    traverse the graph to get full policy context.

    Returns the 'graph_neighbors' part of the policy context package:
    {
        "GV.OC-01": {
            "description": "...",
            "nist_function": "GOVERN",
            "category": "Organizational Context",
            "policies": ["Information Security Policy", ...]
            "siblings": ["GV.OC-02", "GV.OC-03", ...]   ← same category
        },
        ...
    }
    """
    conn = Neo4jConnection()
    result = {}

    for subcat_id in subcategory_ids:
        data = conn.run("""
            MATCH (s:Subcategory {id: $id})
            OPTIONAL MATCH (s)-[:REFERENCES_POLICY]->(p:Policy)
            OPTIONAL MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s)
            OPTIONAL MATCH (f:NistFunction)-[:HAS_CATEGORY]->(c)
            OPTIONAL MATCH (c)-[:HAS_SUBCATEGORY]->(sibling:Subcategory)
            WHERE sibling.id <> $id
            RETURN
                s.id           AS id,
                s.description  AS description,
                f.name         AS nist_function,
                c.name         AS category,
                c.code         AS category_code,
                collect(DISTINCT p.name)      AS policies,
                collect(DISTINCT sibling.id)  AS siblings
        """, {"id": subcat_id})

        if data:
            row = data[0]
            result[subcat_id] = {
                "description":   row.get("description", ""),
                "nist_function": row.get("nist_function", ""),
                "category":      row.get("category", ""),
                "category_code": row.get("category_code", ""),
                "policies":      row.get("policies", []),
                "siblings":      row.get("siblings", []),
            }

    conn.close()
    return result


def get_policies_for_function(nist_function: str) -> List[str]:
    """Get all unique policies under a NIST function — useful for broad queries."""
    conn = Neo4jConnection()
    data = conn.run("""
        MATCH (:NistFunction {name: $fn})-[:HAS_CATEGORY]->(:Category)
              -[:HAS_SUBCATEGORY]->(:Subcategory)
              -[:REFERENCES_POLICY]->(p:Policy)
        RETURN DISTINCT p.name AS policy
        ORDER BY p.name
    """, {"fn": nist_function})
    conn.close()
    return [row["policy"] for row in data]


def get_subcategories_for_policy(policy_name: str) -> List[str]:
    """Reverse lookup — which subcategories reference this policy?"""
    conn = Neo4jConnection()
    data = conn.run("""
        MATCH (s:Subcategory)-[:REFERENCES_POLICY]->(p:Policy {name: $name})
        RETURN s.id AS id, s.description AS description
        ORDER BY s.id
    """, {"name": policy_name})
    conn.close()
    return [{"id": r["id"], "description": r["description"]} for r in data]