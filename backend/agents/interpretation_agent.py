"""
Agent 2 — Policy Interpretation Agent

Uses LLM to classify query type — not keywords.

Query types:
  INCIDENT : Something already happened — needs immediate action
  ACTION   : Employee asking if they can/should do something
  INFO     : Employee asking what a policy means or who is responsible
"""

from typing import Dict
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from config import OPENAI_API_KEY
from utils.token_tracker import extract 

llm = ChatOpenAI(api_key=OPENAI_API_KEY, model="gpt-4o", temperature=0)


# ── Query type classifier ──────────────────────────────────────────────────────

CLASSIFY_PROMPT = PromptTemplate(
    input_variables=["query"],
    template="""
Classify this employee question into exactly one category.

Question: "{query}"

Categories:
- INCIDENT  : Something already happened or is happening right now.
              The employee needs to know what to do urgently.
              Examples: lost device, data breach, accidental access,
              stolen laptop, found suspicious activity, system infected.

- ACTION    : Employee wants to do something and is asking if it is
              allowed or what steps to follow.
              Examples: "can I share data", "am I allowed to",
              "should I install", "may I work remotely".

- INFO      : Employee wants to understand a policy, a process,
              or who is responsible for something.
              Examples: "who is responsible for X", "what does policy say",
              "which document covers", "how does X work".

Rules:
- If the query describes something that ALREADY HAPPENED → INCIDENT
- If the query asks PERMISSION for a future action → ACTION
- If the query seeks EXPLANATION or INFORMATION → INFO
- When unsure between INCIDENT and ACTION → choose INCIDENT
- Output ONLY one word: INCIDENT or ACTION or INFO
"""
)


def detect_query_type(query: str) -> str:
    """Use LLM to classify query type — no keyword matching."""
    chain    = CLASSIFY_PROMPT | llm
    response = chain.invoke({"query": query})
    result   = response.content.strip().upper()

    # Validate — fallback to ACTION if unexpected output
    if result not in {"INCIDENT", "ACTION", "INFO"}:
        print(f"[Interpretation] Unexpected type '{result}' — defaulting to ACTION")
        return "ACTION"

    return result


# ── Interpretation prompt ──────────────────────────────────────────────────────

PROMPT = PromptTemplate(
    input_variables=["query", "query_type", "policy_text"],
    template="""
You are a compliance expert. Query type: {query_type}

Employee said/asked: "{query}"

Relevant NIST CSF policy sections retrieved:
{policy_text}

STRICT RULES:
1. Only use information from the policy sections above
2. Do NOT add roles, names, or processes not in the retrieved text
3. Quote the subcategory ID when referencing a requirement
4. If a detail is not in the retrieved text — do not include it

Instructions by type:
- INCIDENT : Urgent. State what the employee must do NOW.
             Cover: contain, notify, document.
             Be direct — this is an emergency.
- ACTION   : State exactly what the policy allows or restricts.
- INFO     : State exactly what the policy says. Quote the subcategory.

Write 3 to 5 clear sentences grounded in retrieved text only.
"""
)


def run(retrieval_result: Dict) -> Dict:
    query  = retrieval_result["query"]
    chunks = retrieval_result["chunks"]

    # LLM classifies — no keywords
    query_type = detect_query_type(query)
    print(f"\n[Agent 2 - Interpretation] Query type: {query_type}")
    print(f"[Agent 2 - Interpretation] Interpreting {len(chunks)} chunks...")

    policy_text = ""
    for c in chunks:
        policy_text += f"\n- {c['subcategory_id']} ({c['category']}): {c['text'][:300]}\n"

    chain          = PROMPT | llm
    response       = chain.invoke({
        "query":       query,
        "query_type":  query_type,
        "policy_text": policy_text,
    })
    interpretation = response.content.strip()
    tokens = extract(response)
    print(f"[Agent 2 - Interpretation] Done.")
    return {
        **retrieval_result,
        "query_type":     query_type,
        "interpretation": interpretation,
        "tokens_interpretation": tokens
    }