"""
Agent 3 — Compliance Checker Agent

Three query types:
  INFO     → verdict=INFO, score=null
  ACTION   → COMPLIANT / NON_COMPLIANT / NEEDS_REVIEW
  INCIDENT → REQUIRES_ACTION + urgency score

No hardcoded citation rules.
LLM picks citations from retrieved chunks using clear prompt guidance.
Retrieval agent (Milvus + Neo4j intent traversal) ensures right chunks arrive.
"""

from typing import Dict, List
import json
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from config import OPENAI_API_KEY
from utils.token_tracker import extract 

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o", temperature=0)


# ══════════════════════════════════════════════════════════════
# PROMPTS
# ══════════════════════════════════════════════════════════════

INFO_PROMPT = PromptTemplate(
    input_variables=["query", "interpretation", "chunk_descriptions"],
    template="""
You are a compliance expert. An employee asked an informational question:
"{query}"

Policy context: {interpretation}

Available subcategories:
{chunk_descriptions}

Pick subcategories whose description DIRECTLY answers the question.
Skip subcategories about unrelated topics.

Answer in this exact JSON format:
{{
  "verdict": "INFO",
  "score": null,
  "reason": "exact policy statement with subcategory ID reference",
  "citations": ["subcategory IDs that directly answer this question"]
}}

Return ONLY the JSON. No extra text.
"""
)

ACTION_PROMPT = PromptTemplate(
    input_variables=["query", "interpretation", "chunk_descriptions"],
    template="""
You are a compliance checker. Employee is asking about an action:
"{query}"

Policy context: {interpretation}

Available subcategories with exact NIST descriptions:
{chunk_descriptions}

Pick the subcategories that describe what the EMPLOYEE should do.

SELECTION GUIDE:
- For "should I report X": pick subcategories about "providing information to staff"
  or "events analyzed" — NOT about triage or investigation (those happen after)
- For "can I share data": pick data security or access control subcategories
- For "lost/stolen device": pick incident containment + notification subcategories
- For access permission: pick identity and access control subcategories

Answer in this exact JSON format:
{{
  "verdict": "COMPLIANT" or "NON_COMPLIANT" or "NEEDS_REVIEW",
  "score": 0-100,
  "reason": "subcategory ID + exact description that governs this action",
  "citations": ["1 to 3 most directly relevant subcategory IDs"]
}}

- COMPLIANT    = clearly the right action (70-100)
- NEEDS_REVIEW = requires approval (40-69)
- NON_COMPLIANT= violates policy (0-39)

Return ONLY the JSON. No extra text.
"""
)

INCIDENT_PROMPT = PromptTemplate(
    input_variables=["query", "interpretation", "chunk_descriptions"],
    template="""
You are a compliance checker. An employee is dealing with an active incident:
"{query}"

Policy context: {interpretation}

Available subcategories:
{chunk_descriptions}

For incidents, pick subcategories about:
  1. Containing the incident (RS.MI)
  2. Notifying stakeholders (RS.CO)
  3. Declaring the incident (DE.AE-08)
  4. Protecting affected data (PR.DS)

Skip subcategories about: post-incident analysis, monitoring infrastructure,
asset inventory, risk scoring.

Answer in this exact JSON format:
{{
  "verdict": "REQUIRES_ACTION",
  "score": 0-100 (urgency: 80-100=immediately, 60-79=today),
  "reason": "subcategory ID + exact description — what employee must do now",
  "citations": ["2 to 3 most critical subcategory IDs for this incident"]
}}

Return ONLY the JSON. No extra text.
"""
)


def _build_chunk_descriptions(chunks: List[Dict]) -> str:
    """Show subcategory ID + first line of description for precise citation selection."""
    lines = []
    for c in chunks:
        first_line = c["text"].split("\n")[0].strip()[:200]
        lines.append(f"- {c['subcategory_id']} ({c['category']}): {first_line}")
    return "\n".join(lines)


def run(interpretation_result: Dict) -> Dict:
    query          = interpretation_result["query"]
    query_type     = interpretation_result.get("query_type", "ACTION")
    interpretation = interpretation_result["interpretation"]
    chunks         = interpretation_result["chunks"]

    print(f"\n[Agent 3 - Compliance] type={query_type} | chunks={len(chunks)}")

    chunk_descriptions = _build_chunk_descriptions(chunks)

    if query_type == "INFO":
        prompt = INFO_PROMPT
    elif query_type == "INCIDENT":
        prompt = INCIDENT_PROMPT
    else:
        prompt = ACTION_PROMPT

    chain    = prompt | llm
    response = chain.invoke({
        "query":              query,
        "interpretation":     interpretation,
        "chunk_descriptions": chunk_descriptions,
    })

    raw = response.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        compliance = json.loads(raw)
    except json.JSONDecodeError:
        compliance = {
            "verdict":   "NEEDS_REVIEW" if query_type == "ACTION" else
                         "INFO"          if query_type == "INFO"   else
                         "REQUIRES_ACTION",
            "score":     None if query_type == "INFO" else 50,
            "reason":    raw,
            "citations": [c["subcategory_id"] for c in chunks[:2]],
        }
    tokens = extract(response)
    print(f"[Agent 3 - Compliance] verdict={compliance['verdict']} "
          f"score={compliance.get('score','N/A')} "
          f"citations={compliance.get('citations',[])}")

    return {
        **interpretation_result,
        "compliance": compliance,
        "tokens_interpretation": tokens
    }