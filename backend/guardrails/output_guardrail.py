"""
Output Guardrail

Validates the final result from all agents before
returning to the user.

Checks:
  - Verdict is a valid value
  - Score is within 0-100
  - Risk level is valid
  - Recommendations exist
  - Citations exist
  - HIGH/CRITICAL risk triggers escalation
  - No PII leaked in the response
"""

from typing import Dict, Tuple
from openai import OpenAI
from config import OPENAI_API_KEY

client = OpenAI(api_key=OPENAI_API_KEY)

VALID_VERDICTS    = {"COMPLIANT", "NON_COMPLIANT", "NEEDS_REVIEW", "INFO", "REQUIRES_ACTION"}
VALID_RISK_LEVELS = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


# ══════════════════════════════════════════════════════════════
# STRUCTURE VALIDATION
# ══════════════════════════════════════════════════════════════

def _validate_structure(result: Dict) -> Tuple[bool, str]:
    """Check all required fields are present and valid."""

    verdict = result.get("compliance", {}).get("verdict", "")
    if verdict not in VALID_VERDICTS:
        return False, f"Invalid compliance verdict: '{verdict}'"

    score = result.get("compliance", {}).get("score")
    # score can be null for INFO queries — only validate if present
    if score is not None:
        if not isinstance(score, (int, float)) or not (0 <= score <= 100):
            return False, f"Invalid compliance score: '{score}'"

    risk_level = result.get("risk", {}).get("level", "")
    if risk_level not in VALID_RISK_LEVELS:
        return False, f"Invalid risk level: '{risk_level}'"

    steps = result.get("recommendation", {}).get("steps", [])
    if not isinstance(steps, list) or len(steps) == 0:
        return False, "No recommendations were generated."

    citations = result.get("compliance", {}).get("citations", [])
    if not isinstance(citations, list) or len(citations) == 0:
        return False, "No policy citations were provided."

    # HIGH or CRITICAL must escalate
    if risk_level in {"HIGH", "CRITICAL"}:
        escalate = result.get("recommendation", {}).get("escalate", False)
        if not escalate:
            # Auto-fix instead of blocking
            result["recommendation"]["escalate"]    = True
            result["recommendation"]["escalate_to"] = "Security Team"
            print("[Output Guardrail] Auto-fixed: HIGH/CRITICAL risk must escalate.")

    return True, ""


# ══════════════════════════════════════════════════════════════
# PII CHECK ON OUTPUT
# ══════════════════════════════════════════════════════════════

def _check_output_pii(result: Dict) -> Dict:
    """
    Check if any PII leaked into the response text.
    Uses Presidio on the interpretation and summary fields.
    """
    try:
        from presidio_analyzer import AnalyzerEngine
        analyzer = AnalyzerEngine()

        # Check interpretation and summary for PII
        fields_to_check = [
            result.get("interpretation", ""),
            result.get("recommendation", {}).get("summary", ""),
        ]

        pii_in_output = []
        for text in fields_to_check:
            if text:
                findings = analyzer.analyze(
                    text=text,
                    language="en",
                    entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER",
                              "CREDIT_CARD", "US_SSN", "IP_ADDRESS"],
                )
                pii_in_output.extend([f.entity_type for f in findings])

        if pii_in_output:
            print(f"[Output Guardrail] PII detected in output: {pii_in_output}")
            result["warning"] = f"Response may contain sensitive information: {pii_in_output}"

    except ImportError:
        pass  # Presidio not installed, skip

    return result


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def validate(result: Dict) -> Dict:
    """
    Validate the final result before returning to user.

    Returns the result dict — either clean or with a warning field.
    Never blocks output — just flags issues and auto-fixes where possible.
    """
    # Structure check
    ok, reason = _validate_structure(result)
    if not ok:
        print(f"[Output Guardrail] Structure issue: {reason}")
        result["warning"] = reason

    # PII check on output text
    result = _check_output_pii(result)

    print("[Output Guardrail] Output validation complete.")
    return result