import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.search_profile_keyword_schemas import SearchProfileKeywordCreate


class SearchProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    profession: Optional[str] = None
    profession_description: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    target_clients: Optional[str] = None
    preferred_niches: List[str] = Field(default_factory=list)
    excluded_niches: List[str] = Field(default_factory=list)
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    currency: str = "RUB"
    geography: Optional[str] = None
    languages: List[str] = Field(default_factory=list)
    lead_types: List[str] = Field(default_factory=list)
    notification_threshold: int = 60
    is_active: bool = True
    ai_profile_context: Optional[str] = None
    created_at: dt.datetime
    updated_at: dt.datetime


class SearchProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    profession: Optional[str] = Field(default=None, max_length=255)
    profession_description: Optional[str] = Field(default=None, max_length=4000)
    services: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    target_clients: Optional[str] = Field(default=None, max_length=255)
    preferred_niches: List[str] = Field(default_factory=list)
    excluded_niches: List[str] = Field(default_factory=list)
    min_budget: Optional[float] = Field(default=None, ge=0)
    max_budget: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(default="RUB", max_length=8)
    geography: Optional[str] = Field(default=None, max_length=255)
    languages: List[str] = Field(default_factory=list)
    lead_types: List[str] = Field(default_factory=list)
    notification_threshold: int = Field(default=60, ge=0, le=100)
    is_active: bool = True
    ai_profile_context: Optional[str] = None
    # Onboarding (Этап 4) passes its AI-generated (and possibly user-
    # edited) starter keyword set here so it's used INSTEAD OF the
    # generic global-catalog seed (see app/api/search_profiles.py) — a
    # profile created without onboarding still gets seeded from the
    # global catalog when this is omitted/empty.
    keywords: List[SearchProfileKeywordCreate] = Field(default_factory=list)


class SearchProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    profession: Optional[str] = Field(default=None, max_length=255)
    profession_description: Optional[str] = Field(default=None, max_length=4000)
    services: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    technologies: Optional[List[str]] = None
    target_clients: Optional[str] = Field(default=None, max_length=255)
    preferred_niches: Optional[List[str]] = None
    excluded_niches: Optional[List[str]] = None
    min_budget: Optional[float] = Field(default=None, ge=0)
    max_budget: Optional[float] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, max_length=8)
    geography: Optional[str] = Field(default=None, max_length=255)
    languages: Optional[List[str]] = None
    lead_types: Optional[List[str]] = None
    notification_threshold: Optional[int] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None
    ai_profile_context: Optional[str] = None
