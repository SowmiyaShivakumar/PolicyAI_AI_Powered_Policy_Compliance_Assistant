"""
Orchestrator — Runs all 5 agents in sequence with guardrails.

Flow:
  Query
    → Input Guardrail     (validate query)
    → Agent 1: Retrieval
    → Agent 2: Interpretation
    → Agent 3: Compliance
    → Agent 4: Risk
    → Agent 5: Recommendation
    → Output Guardrail    (validate result)
    → Final response
"""

from typing import Dict
from agents import (
    retrieval_agent,
    interpretation_agent,
    compliance_agent,
    risk_agent,
    recommendation_agent,
)
from guardrails.input_guardrail  import validate as validate_input
from guardrails.output_guardrail import validate as validate_output
from utils.token_tracker import summarise as summarise_tokens


def run(query: str) -> Dict:
    """
    Main entry point. Pass a user query, get full compliance analysis.
    """
    print("\n" + "="*50)
    print(f"  Query: {query}")
    print("="*50)

    # ── Input Guardrail ───────────────────────────────
    input_check = validate_input(query)
    if not input_check["valid"]:
        return {
            "error":   "invalid_input",
            "message": input_check["message"],
            "query":   query,
        }

    # Use clean query (PII removed) for all agents
    clean_query = input_check["clean_query"]
    if input_check["pii_found"]:
        print(f"[Guardrail] PII removed from query: {input_check['pii_found']}")

    print("[Guardrail] Input valid. Running agents...")

    # ── Run agents in sequence ────────────────────────
    # top_k=6 gives broader coverage — compliance agent
    # filters to 1-3 most relevant citations anyway
    result = retrieval_agent.run(clean_query, top_k=6)
    result = interpretation_agent.run(result)
    result = compliance_agent.run(result)
    result = risk_agent.run(result)
    result = recommendation_agent.run(result)

    # ── Build clean final response ────────────────────
    final = {
        "query":          query,
        "query_type":     result.get("query_type", "ACTION"),
        "interpretation": result["interpretation"],
        "compliance": {
            "verdict":   result["compliance"]["verdict"],
            "score":     result["compliance"].get("score") or result["compliance"].get("compliance_score"),
            "reason":    result["compliance"]["reason"],
            "citations": result["compliance"]["citations"],
        },
        "risk": {
            "level":            result["risk"]["risk_level"],
            "reason":           result["risk"]["risk_reason"],
            "affected":         result["risk"]["affected_functions"],
            "potential_impact": result["risk"]["potential_impact"],
        },
        "recommendation": {
            "steps":       result["recommendation"]["recommendations"],
            "escalate":    result["recommendation"]["escalate"],
            "escalate_to": result["recommendation"].get("escalate_to"),
            "summary":     result["recommendation"]["summary"],
        },
        "policy_references": result["policy_references"],
    }

    # ── Collect token usage from all agents ───────────────────
    final["token_usage"] = summarise_tokens({
        "interpretation":  result.get("tokens_interpretation", {"input":0,"output":0}),
        "compliance":      result.get("tokens_compliance",     {"input":0,"output":0}),
        "risk":            result.get("tokens_risk",           {"input":0,"output":0}),
        "recommendation":  result.get("tokens_recommendation", {"input":0,"output":0}),
    })

    # ── Output Guardrail ──────────────────────────────
    final = validate_output(final)

    score_display = final['compliance']['score']
    score_display = f"{score_display}/100" if score_display is not None else "N/A (info query)"

    print("\n" + "="*50)
    print("  FINAL RESULT")
    print("="*50)
    print(f"  Query Type : {final['query_type']}")
    print(f"  Verdict    : {final['compliance']['verdict']}")
    print(f"  Score      : {score_display}")
    print(f"  Risk       : {final['risk']['level']}")
    print(f"  Escalate   : {final['recommendation']['escalate']}")
    print(f"  Summary    : {final['recommendation']['summary']}")
    print(f"  Tokens     : {final['token_usage']['total_tokens']} "
          f"(in={final['token_usage']['total_input']} "
          f"out={final['token_usage']['total_output']}) "
          f"~${final['token_usage']['estimated_cost_usd']}")
    print("="*50)

    return final