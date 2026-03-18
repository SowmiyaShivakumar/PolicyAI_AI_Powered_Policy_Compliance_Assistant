"""
Input Guardrail

Three layers of protection before query reaches agents:

Layer 1 — Custom rules     : length, topic relevance
Layer 2 — Presidio         : detect and anonymise PII
Layer 3 — OpenAI Moderation: block harmful/malicious content
"""

from typing import Dict, Tuple
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)


# ── Compliance keywords — query must relate to at least one ──────────────────
COMPLIANCE_KEYWORDS = [
    "can i", "should i", "allowed", "permitted", "policy", "compliance",
    "share", "access", "data", "report", "escalate", "restrict", "store",
    "send", "transfer", "install", "use", "remote", "vpn", "password",
    "encrypt", "backup", "incident", "breach", "violation", "risk",
    "approve", "authorization", "gdpr", "nist", "security", "audit",
    "working", "travel", "country", "customer", "project", "team",
]

# ── Clearly off-topic keywords ───────────────────────────────────────────────
OFF_TOPIC_KEYWORDS = [
    "weather", "recipe", "sports", "movie", "music", "game",
    "joke", "poem", "story", "stock", "crypto", "celebrity",
]


# ══════════════════════════════════════════════════════════════
# LAYER 1 — Custom rules
# ══════════════════════════════════════════════════════════════

def _custom_rules(query: str) -> Tuple[bool, str]:
    """Basic validation rules."""

    if not query or not query.strip():
        return False, "Query cannot be empty."

    if len(query.strip()) < 10:
        return False, "Query is too short. Please ask a complete question."

    if len(query.strip()) > 500:
        return False, "Query is too long. Please keep it under 500 characters."

    query_lower = query.lower()

    for word in OFF_TOPIC_KEYWORDS:
        if word in query_lower:
            return False, "This system only answers compliance and policy questions."

    has_keyword = any(kw in query_lower for kw in COMPLIANCE_KEYWORDS)
    if not has_keyword:
        return False, "Please ask a question related to compliance, policy, or security."

    return True, ""


# ══════════════════════════════════════════════════════════════
# LAYER 2 — Presidio PII detection and anonymisation
# ══════════════════════════════════════════════════════════════

def _presidio_anonymise(query: str) -> Tuple[str, list]:
    """
    Detect and anonymise PII using Microsoft Presidio.
    Returns cleaned query + list of what was found.
    """
    try:
        from presidio_analyzer  import AnalyzerEngine
        from presidio_anonymizer import AnonymizerEngine

        analyzer   = AnalyzerEngine()
        anonymizer = AnonymizerEngine()

        # Analyse for PII
        results = analyzer.analyze(
            text=query,
            language="en",
            entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                      "CREDIT_CARD", "US_SSN", "IP_ADDRESS"],
        )

        if not results:
            return query, []

        # Anonymise detected PII
        anonymized = anonymizer.anonymize(text=query, analyzer_results=results)
        found_pii  = [r.entity_type for r in results]

        return anonymized.text, found_pii

    except ImportError:
        # Presidio not installed — skip this layer
        print("[guardrail] Presidio not installed, skipping PII check.")
        return query, []

    except Exception as e:
        print(f"[guardrail] Presidio error: {e}")
        return query, []


# ══════════════════════════════════════════════════════════════
# LAYER 3 — OpenAI Moderation API
# ══════════════════════════════════════════════════════════════

def _openai_moderation(query: str) -> Tuple[bool, str]:
    """
    Call OpenAI Moderation API to detect harmful content.
    Free to use — no tokens consumed.
    """
    try:
        response = client.moderations.create(input=query)
        result   = response.results[0]

        if result.flagged:
            # Find which category was triggered
            categories = result.categories.model_dump()
            flagged    = [k for k, v in categories.items() if v]
            return False, f"Query flagged for: {', '.join(flagged)}"

        return True, ""

    except Exception as e:
        print(f"[guardrail] OpenAI moderation error: {e}")
        # If moderation API fails, allow the query through
        return True, ""


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def validate(query: str) -> Dict:
    """
    Run all three layers on the input query.

    Returns:
    {
        "valid":      True/False,
        "clean_query": sanitised query (PII removed),
        "message":    reason if blocked,
        "pii_found":  list of PII types detected and removed
    }
    """

    # Layer 1 — custom rules
    ok, reason = _custom_rules(query)
    if not ok:
        print(f"[Input Guardrail] Blocked by custom rules: {reason}")
        return {"valid": False, "clean_query": query, "message": reason, "pii_found": []}

    # Layer 2 — Presidio PII anonymisation
    clean_query, pii_found = _presidio_anonymise(query)
    if pii_found:
        print(f"[Input Guardrail] PII detected and removed: {pii_found}")

    # Layer 3 — OpenAI moderation
    ok, reason = _openai_moderation(clean_query)
    if not ok:
        print(f"[Input Guardrail] Blocked by moderation: {reason}")
        return {"valid": False, "clean_query": clean_query, "message": reason, "pii_found": pii_found}

    print(f"[Input Guardrail] Query passed all checks.")
    return {
        "valid":       True,
        "clean_query": clean_query,
        "message":     "",
        "pii_found":   pii_found,
    }