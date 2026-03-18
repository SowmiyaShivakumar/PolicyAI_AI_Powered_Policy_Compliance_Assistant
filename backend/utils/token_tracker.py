"""
Token Usage Tracker

Tracks input and output tokens for every LLM call.
Supports both:
- LangChain ChatOpenAI responses
- Direct OpenAI client responses
"""

from typing import Dict

# GPT-4o pricing per token
INPUT_COST_PER_TOKEN  = 2.50  / 1_000_000
OUTPUT_COST_PER_TOKEN = 10.00 / 1_000_000


def extract(response) -> Dict:
    """
    Extract token counts from LangChain ChatOpenAI response.
    Works for both new and older LangChain versions.
    """
    try:
        # ✅ NEW LangChain (preferred)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            return {
                "input":  usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cached": usage.get("input_token_details", {}).get("cache_read", 0),
            }

        # ⚠️ OLD fallback
        usage = response.response_metadata.get("token_usage", {})
        details = usage.get("prompt_tokens_details", {})

        return {
            "input":  usage.get("prompt_tokens", 0),
            "output": usage.get("completion_tokens", 0),
            "cached": details.get("cached_tokens", 0),
        }

    except Exception as e:
        print(f"⚠️ Token extraction failed: {e}")
        return {"input": 0, "output": 0, "cached": 0}


def extract_from_openai(response) -> Dict:
    """Extract token counts from direct OpenAI client response."""
    try:
        return {
            "input":  response.usage.prompt_tokens,
            "output": response.usage.completion_tokens,
            "cached": 0,
        }
    except Exception:
        return {"input": 0, "output": 0, "cached": 0}


def summarise(usage_per_agent: Dict) -> Dict:
    """Aggregate token usage across all agents."""
    total_input  = sum(v.get("input", 0)  for v in usage_per_agent.values())
    total_output = sum(v.get("output", 0) for v in usage_per_agent.values())
    total        = total_input + total_output

    cost = round(
        total_input  * INPUT_COST_PER_TOKEN +
        total_output * OUTPUT_COST_PER_TOKEN,
        6
    )

    return {
        "per_agent":          usage_per_agent,
        "total_input":        total_input,
        "total_output":       total_output,
        "total_tokens":       total,
        "estimated_cost_usd": cost,
    }