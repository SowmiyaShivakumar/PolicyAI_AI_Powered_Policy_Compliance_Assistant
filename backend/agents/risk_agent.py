"""
Agent 4 — Risk Assessment Agent

INFO     → no risky action, just clarify context
ACTION   → assess risk of the action
INCIDENT → assess severity of the incident
"""

from typing import Dict
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from config import OPENAI_API_KEY
from utils.token_tracker import extract

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o", temperature=0)

INFO_PROMPT = PromptTemplate(
    input_variables=["query", "affected_functions"],
    template="""
You are a cybersecurity risk assessor.

An employee asked a clarification question (not a risky action):
"{query}"

Affected NIST functions: {affected_functions}

Answer in this exact JSON format:
{{
  "risk_level": "LOW",
  "risk_reason": "This is a clarification question, not a risky action.",
  "affected_functions": {affected_functions},
  "potential_impact": "No direct risk — this is an informational query about governance responsibilities."
}}

Return ONLY the JSON. No extra text.
"""
)

ACTION_PROMPT = PromptTemplate(
    input_variables=["query", "verdict", "score", "affected_functions"],
    template="""
You are a cybersecurity risk assessor.

Employee action: "{query}"
Compliance verdict: {verdict}
Compliance score: {score}/100
Affected NIST functions: {affected_functions}

Answer in this exact JSON format:
{{
  "risk_level": "LOW" or "MEDIUM" or "HIGH" or "CRITICAL",
  "risk_reason": "specific reason referencing the NIST function and what could be violated",
  "affected_functions": {affected_functions},
  "potential_impact": "specific consequence if this action proceeds without compliance"
}}

Return ONLY the JSON. No extra text.
"""
)

INCIDENT_PROMPT = PromptTemplate(
    input_variables=["query", "verdict", "score", "affected_functions"],
    template="""
You are a cybersecurity risk assessor.

An incident has occurred: "{query}"
Urgency score: {score}/100
Affected NIST functions: {affected_functions}

Answer in this exact JSON format:
{{
  "risk_level": "HIGH" or "CRITICAL",
  "risk_reason": "specific reason why this incident poses a risk",
  "affected_functions": {affected_functions},
  "potential_impact": "specific data, system, or compliance impact if not addressed immediately"
}}

Return ONLY the JSON. No extra text.
"""
)


def run(compliance_result: Dict) -> Dict:
    query      = compliance_result["query"]
    query_type = compliance_result.get("query_type", "ACTION")
    compliance = compliance_result["compliance"]
    chunks     = compliance_result["chunks"]

    print(f"\n[Agent 4 - Risk] Assessing risk (type: {query_type})...")

    if query_type == "INFO":
        # INFO — derive from cited subcategories only
        cited_ids = [c.split(" - ")[0].strip() for c in compliance.get("citations", [])]
        affected_functions = list(set(
            c["nist_function"] for c in chunks
            if c["subcategory_id"] in cited_ids
        ))
        if not affected_functions and chunks:
            affected_functions = [chunks[0]["nist_function"]]
    elif query_type == "ACTION" or query_type == "INCIDENT":
        # ACTION/INCIDENT — also derive from citations the compliance agent selected
        # This prevents noise from unrelated retrieved chunks
        cited_ids = [c.split(" - ")[0].strip() for c in compliance.get("citations", [])]
        affected_functions = list(set(
            c["nist_function"] for c in chunks
            if c["subcategory_id"] in cited_ids
        ))
        # Fallback to all chunks if citations don't match
        if not affected_functions:
            affected_functions = list(set(c["nist_function"] for c in chunks))
    else:
        affected_functions = list(set(c["nist_function"] for c in chunks))

    if query_type == "INFO":
        prompt = INFO_PROMPT
        inputs = {
            "query":             query,
            "affected_functions": json.dumps(affected_functions),
        }
    elif query_type == "INCIDENT":
        prompt = INCIDENT_PROMPT
        inputs = {
            "query":             query,
            "verdict":           compliance["verdict"],
            "score":             compliance.get("score", 80),
            "affected_functions": json.dumps(affected_functions),
        }
    else:
        prompt = ACTION_PROMPT
        inputs = {
            "query":             query,
            "verdict":           compliance["verdict"],
            "score":             compliance.get("score", 50),
            "affected_functions": json.dumps(affected_functions),
        }

    chain    = prompt | llm
    response = chain.invoke(inputs)

    raw = response.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        risk = json.loads(raw)
    except json.JSONDecodeError:
        risk = {
            "risk_level":         "LOW" if query_type == "INFO" else "MEDIUM",
            "risk_reason":        raw,
            "affected_functions": affected_functions,
            "potential_impact":   "Unable to assess.",
        }

    print(f"[Agent 4 - Risk] Risk Level: {risk['risk_level']}")
    tokens = extract(response)
    return {
        **compliance_result,
        "risk": risk,
        "tokens_interpretation": tokens
    }