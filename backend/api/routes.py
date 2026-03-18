"""
API Routes — All endpoints for the compliance assistant.

Endpoints:
  POST /query          → main compliance query (runs all 5 agents)
  GET  /health         → check if API is running
  GET  /search         → hybrid search only (no agents)
"""

from fastapi import APIRouter, HTTPException
from api.models import QueryRequest, QueryResponse, ErrorResponse
from agents.orchestrator import run as run_agents
from retrieval.hybrid_search import hybrid_search

router = APIRouter()


# ── Health check ──────────────────────────────────────────────────────────────

@router.get("/health", tags=["Health"])
def health():
    """Check if the API is running."""
    return {"status": "ok", "message": "Policy Compliance API is running."}


# ── Main compliance query endpoint ────────────────────────────────────────────

@router.post(
    "/query",
    tags=["Compliance"],
    summary="Ask a compliance question",
    description="Runs all 5 agents and returns full compliance analysis.",
)
def compliance_query(request: QueryRequest):
    """
    Main endpoint — takes a compliance question,
    runs all 5 agents, returns full analysis.
    """
    result = run_agents(request.query)

    # If guardrail blocked the input
    if "error" in result:
        raise HTTPException(
            status_code=400,
            detail=result["message"]
        )

    return result


# ── Search only endpoint (no agents) ─────────────────────────────────────────

@router.get(
    "/search",
    tags=["Search"],
    summary="Search policy chunks",
    description="Runs hybrid search only — no agents, no LLM calls.",
)
def search(
    query: str,
    top_k: int = 5,
    nist_function: str = None,
    category: str = None,
):
    """
    Lightweight endpoint — just returns matching policy chunks.
    Useful for testing retrieval without running full agent pipeline.
    """
    if not query or len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short.")

    results = hybrid_search(
        query=query,
        top_k=top_k,
        nist_function=nist_function,
        category=category,
    )

    return {
        "query":   query,
        "results": results,
        "count":   len(results),
    }