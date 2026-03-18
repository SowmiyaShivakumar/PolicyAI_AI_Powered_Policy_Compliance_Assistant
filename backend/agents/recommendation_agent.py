"""
Agent 5 — Recommendation Agent

INFO     → guide on governance process
ACTION   → specific steps to comply or get approval
INCIDENT → immediate response steps

Policy priority filter:
  Primary policies surface first (Information Security Policy,
  Access Control Policy, Personnel Security Policy, Incident Response Policy)
  Technical standards (Vulnerability Scanning, Security Logging) deprioritised
"""

from typing import Dict, List
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from config import OPENAI_API_KEY
from utils.token_tracker import extract 

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o", temperature=0)

# ── Policy priority tiers ─────────────────────────────────────────────────────
# Tier 1 = primary policies (always surface these first)
# Tier 2 = secondary standards (only if no tier 1 found)
TIER1_POLICIES = [
    "Information Security Policy",
    "Access Control Policy",
    "Personnel Security Policy",
    "Incident Response Policy",
    "Computer Security Threat Response Policy",
    "Identification and Authentication Policy",
    "Acceptable Use of Information Technology Resource Policy",
    "Security Awareness and Training Policy",
    "System and Communications Protection Policy",
    "Information Classification Standard",
    "Cyber Incident Response Standard",
    "Contingency Planning Policy",
]

TIER2_POLICIES = [
    "Vulnerability Scanning Standard",
    "Security Logging Standard",
    "Auditing and Accountability Standard",
    "System and Information Integrity Policy",
    "Secure Coding Standard",
    "Patch Management Standard",
    "Remote Access Standard",
]


def _priority_filter(policy_names: List[str], max_count: int = 3) -> List[str]:
    """
    Return top policies with Tier 1 prioritised over Tier 2.
    Never return a Tier 2 policy if a Tier 1 one is available.
    """
    tier1 = [p for p in policy_names if p in TIER1_POLICIES]
    tier2 = [p for p in policy_names if p in TIER2_POLICIES]
    other = [p for p in policy_names if p not in TIER1_POLICIES
             and p not in TIER2_POLICIES]

    # Prefer: other (org-specific) > tier1 > tier2
    ordered = list(dict.fromkeys(other + tier1 + tier2))

    # If we have tier1, never include tier2
    if tier1:
        ordered = [p for p in ordered if p not in TIER2_POLICIES]

    return ordered[:max_count]


# ── Prompts ───────────────────────────────────────────────────────────────────

INFO_PROMPT = PromptTemplate(
    input_variables=["query", "reason", "policies"],
    template="""
You are a compliance advisor. An employee asked an informational question:
"{query}"

Policy answer: {reason}
Relevant policy documents: {policies}

Answer in this exact JSON format:
{{
  "recommendations": [
    "step 1: reference the exact subcategory ID and what it states",
    "step 2: name the exact policy document from the list above",
    "step 3: describe the exact process based on the policy text"
  ],
  "escalate": false,
  "escalate_to": null,
  "summary": "one sentence directly answering using only what the policy states"
}}

STRICT RULES:
- Only use roles explicitly in the policy answer — no invented roles
- Policy names must come from the provided list only
- No generic awareness training suggestions
- Summary must directly answer the question

Return ONLY the JSON. No extra text.
"""
)

ACTION_PROMPT = PromptTemplate(
    input_variables=["query", "verdict", "score", "risk_level",
                     "risk_reason", "policies"],
    template="""
You are a compliance advisor:

Employee asked: "{query}"
Verdict: {verdict} | Score: {score}/100 | Risk: {risk_level}
Risk reason: {risk_reason}
Available policy documents: {policies}

Answer in this exact JSON format:
{{
  "recommendations": [
    "step 1: what employee should do — reference exact policy from list",
    "step 2: who to contact or what process to follow",
    "step 3: how to document or follow up"
  ],
  "escalate": true or false,
  "escalate_to": "exact team name or null",
  "summary": "one sentence telling employee exactly what to do"
}}

STRICT RULES:
- Use ONLY policy names from the provided list
- Each step must be actionable and specific
- NEEDS_REVIEW → escalate=true, escalate_to="Information Security Team"
- NON_COMPLIANT → escalate=true, escalate_to="CISO / Compliance Officer"
- COMPLIANT → escalate=false

Return ONLY the JSON. No extra text.
"""
)

INCIDENT_PROMPT = PromptTemplate(
    input_variables=["query", "risk_level", "risk_reason", "policies"],
    template="""
You are a compliance advisor. An incident occurred:
"{query}"

Risk: {risk_level} | Reason: {risk_reason}
Available policy documents: {policies}

Answer in this exact JSON format:
{{
  "recommendations": [
    "immediate step 1 — what to do right now",
    "immediate step 2 — who to notify",
    "immediate step 3 — how to document"
  ],
  "escalate": true,
  "escalate_to": "Incident Response Team",
  "summary": "one sentence on the most urgent action right now"
}}

Return ONLY the JSON. No extra text.
"""
)


def run(risk_result: Dict) -> Dict:
    query      = risk_result["query"]
    query_type = risk_result.get("query_type", "ACTION")
    compliance = risk_result["compliance"]
    risk       = risk_result["risk"]
    chunks     = risk_result["chunks"]

    print(f"\n[Agent 5 - Recommendation] Generating ({query_type})...")

    # ── Get policies from cited chunks only ───────────────────────────────────
    cited_ids = [
        c.split(" - ")[0].strip()
        for c in compliance.get("citations", [])
    ]

    raw_policies = []
    for c in chunks:
        if c["subcategory_id"] in cited_ids:
            gc = risk_result["graph_context"].get(c["subcategory_id"], {})
            raw_policies.extend(gc.get("policies", []))

    # Fallback — top chunk if no cited match
    if not raw_policies and chunks:
        gc = risk_result["graph_context"].get(chunks[0]["subcategory_id"], {})
        raw_policies = gc.get("policies", [])

    # Apply priority filter — surfaces primary policies, hides tech standards
    policy_names = _priority_filter(list(dict.fromkeys(raw_policies)), max_count=3)
    print(f"[Agent 5 - Recommendation] Filtered policies: {policy_names}")

    # ── Build inputs per query type ───────────────────────────────────────────
    if query_type == "INFO":
        prompt = INFO_PROMPT
        inputs = {
            "query":    query,
            "reason":   compliance["reason"],
            "policies": json.dumps(policy_names),
        }
    elif query_type == "INCIDENT":
        prompt = INCIDENT_PROMPT
        inputs = {
            "query":       query,
            "risk_level":  risk["risk_level"],
            "risk_reason": risk["risk_reason"],
            "policies":    json.dumps(policy_names),
        }
    else:
        prompt = ACTION_PROMPT
        inputs = {
            "query":       query,
            "verdict":     compliance["verdict"],
            "score":       compliance.get("score", 50),
            "risk_level":  risk["risk_level"],
            "risk_reason": risk["risk_reason"],
            "policies":    json.dumps(policy_names),
        }

    chain    = prompt | llm
    response = chain.invoke(inputs)

    raw = response.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        recommendation = json.loads(raw)
    except json.JSONDecodeError:
        recommendation = {
            "recommendations": ["Consult the Information Security Policy."],
            "escalate":        True,
            "escalate_to":     "Information Security Team",
            "summary":         raw,
        }

    print(f"[Agent 5 - Recommendation] Escalate: {recommendation['escalate']}")
    tokens = extract(response)
    return {
        **risk_result,
        "recommendation":    recommendation,
        "policy_references": policy_names,
        "tokens_interpretation": tokens
    }