"""Pydantic v2 request/response schemas for the Lead API."""
import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import LeadStatus


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_item_id: int
    is_lead: bool
    lead_probability: float
    lead_score: int
    lead_type: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    business_niche: Optional[str] = None
    project_description: Optional[str] = None
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    currency: Optional[str] = None
    urgency: Optional[str] = None
    complexity: Optional[str] = None
    estimated_value: Optional[str] = None
    summary: Optional[str] = None
    reasoning: Optional[str] = None
    positive_signals: List[str] = Field(default_factory=list)
    negative_signals: List[str] = Field(default_factory=list)
    intent_score: int = 0
    intent_signals: List[str] = Field(default_factory=list)
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime


class LeadWithContextRead(LeadRead):
    """Lead detail view — includes the originating RawItem's text/author/source."""

    raw_text: str
    raw_url: Optional[str] = None
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    source_id: Optional[int] = None
    source_name: Optional[str] = None


class LeadUpdate(BaseModel):
    status: Optional[str] = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {s.value for s in LeadStatus}:
            allowed = ", ".join(s.value for s in LeadStatus)
            raise ValueError(f"must be one of: {allowed}")
        return value
