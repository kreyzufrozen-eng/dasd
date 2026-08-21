"""Onboarding: "describe yourself in plain text" -> AI-generated
SearchProfile draft. The AI response schema, validated the same way
LeadAnalysis is (see app/schemas/ai_analysis.py) — never trust raw JSON
from the model without Pydantic validation.
"""
from typing import List

from pydantic import BaseModel, Field, field_validator

from app.models.enums import KeywordCategory


class ProfileDraftRequest(BaseModel):
    description: str = Field(min_length=10, max_length=4000)


class SuggestedKeyword(BaseModel):
    text: str
    category: str
    weight: float = Field(default=1.0, ge=0.0, le=10.0)

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        allowed = {c.value for c in KeywordCategory}
        if value not in allowed:
            raise ValueError(f"must be one of: {', '.join(sorted(allowed))}")
        return value


class ProfileDraft(BaseModel):
    profession: str
    services: List[str] = Field(default_factory=list)
    suggested_orders: List[str] = Field(default_factory=list)
    suggested_exclusions: List[str] = Field(default_factory=list)
    suggested_keywords: List[SuggestedKeyword] = Field(default_factory=list)
    ai_profile_context: str = ""
    summary_direct: str = ""
    summary_potential: str = ""
    summary_hidden: str = ""
    summary_excluded: str = ""
