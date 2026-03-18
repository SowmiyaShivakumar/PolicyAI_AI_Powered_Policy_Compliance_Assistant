"""
API Models — Request and Response schemas using Pydantic.
FastAPI uses these to validate input and document the API automatically.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


# ── Request ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The compliance question from the employee",
        example="Can I share customer data with another team?"
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of policy chunks to retrieve"
    )


# ── Nested response models ────────────────────────────────────────────────────

class ComplianceResult(BaseModel):
    verdict:   str          # COMPLIANT / NON_COMPLIANT / NEEDS_REVIEW
    score:     float        # 0-100
    reason:    str
    citations: List[str]    # subcategory IDs cited


class RiskResult(BaseModel):
    level:            str   # LOW / MEDIUM / HIGH / CRITICAL
    reason:           str
    affected:         List[str]
    potential_impact: str


class RecommendationResult(BaseModel):
    steps:       List[str]
    escalate:    bool
    escalate_to: Optional[str]
    summary:     str


# ── Main response ─────────────────────────────────────────────────────────────

class QueryResponse(BaseModel):
    query:              str
    interpretation:     str
    compliance:         ComplianceResult
    risk:               RiskResult
    recommendation:     RecommendationResult
    policy_references:  List[str]
    warning:            Optional[str] = None  # set if output guardrail flagged something


# ── Error response ────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error:   str
    message: str
    query:   str