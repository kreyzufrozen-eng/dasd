"""Pydantic schema the AI's JSON response must validate against.

Any AIProvider implementation MUST return a LeadAnalysis (or raise) —
never a raw dict — so every caller downstream gets the same guarantees.
"""
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class BudgetInfo(BaseModel):
    mentioned: bool = False
    min: Optional[float] = None
    max: Optional[float] = None
    currency: Optional[str] = None


class LeadAnalysis(BaseModel):
    is_lead: bool
    lead_probability: float = Field(ge=0.0, le=1.0)
    lead_type: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    project_description: Optional[str] = None
    business_niche: Optional[str] = None
    budget: BudgetInfo = Field(default_factory=BudgetInfo)
    urgency: str = "low"
    project_complexity: str = "low"
    intent: str = "unrelated"
    # Dedicated, structured signal — deliberately NOT inferred from
    # free-text negative_signals (substring-matching a natural-language
    # list the model fills inconsistently was unreliable in practice: it
    # would sometimes describe self-advertising correctly in `summary`
    # without ever setting is_lead=False or adding a matching phrase to
    # negative_signals). This field is the single source of truth used to
    # force is_lead=False downstream, regardless of what the model set.
    is_self_advertising: bool = False
    estimated_value: str = "low"
    summary: str = ""
    reasoning_short: str = ""
    positive_signals: List[str] = Field(default_factory=list)
    negative_signals: List[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Independent of is_lead/lead_probability: how likely this author will
    # need a website SOON even though they aren't asking today (new
    # venture, outdated site, no inbound-lead channel yet, etc). 0 when
    # there's no such signal at all — most messages.
    intent_score: int = Field(default=0, ge=0, le=100)
    intent_signals: List[str] = Field(default_factory=list)

    @field_validator("urgency", "project_complexity", "estimated_value")
    @classmethod
    def _validate_level(cls, value: str) -> str:
        allowed = {"low", "medium", "high"}
        if value not in allowed:
            raise ValueError(f"must be one of {allowed}, got {value!r}")
        return value

    @field_validator("intent")
    @classmethod
    def _validate_intent(cls, value: str) -> str:
        allowed = {
            "looking_for_contractor",
            "problem_statement",
            "recommendation_request",
            "unrelated",
        }
        if value not in allowed:
            raise ValueError(f"must be one of {allowed}, got {value!r}")
        return value
