import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AdminOverview(BaseModel):
    total_users: int
    total_search_profiles: int
    total_sources: int
    active_sources: int
    total_keywords: int
    total_raw_items: int
    total_leads: int
    leads_today: int
    database_status: str


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: Optional[str] = None
    telegram_username: Optional[str] = None
    name: Optional[str] = None
    is_admin: bool
    is_active: bool
    created_at: dt.datetime
    last_login_at: Optional[dt.datetime] = None
    search_profile_count: int
    lead_count: int


class AdminUserUpdate(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None


class AdminProfileSourceRead(BaseModel):
    id: int
    name: str
    type: str
    url: Optional[str] = None
    enabled: bool
    # True when this catalog Source was created by the user themselves
    # (their own "мой канал" custom-add) rather than picked from the
    # shared/admin-seeded catalog — see Source.added_by_user_id.
    is_custom: bool


class AdminProfileKeywordRead(BaseModel):
    text: str
    category: str
    enabled: bool


class AdminSearchProfileDetail(BaseModel):
    id: int
    name: str
    profession: Optional[str] = None
    profession_description: Optional[str] = None
    services: list[str] = Field(default_factory=list)
    target_clients: Optional[str] = None
    preferred_niches: list[str] = Field(default_factory=list)
    excluded_niches: list[str] = Field(default_factory=list)
    geography: Optional[str] = None
    is_active: bool
    created_at: dt.datetime
    sources: list[AdminProfileSourceRead] = Field(default_factory=list)
    keywords: list[AdminProfileKeywordRead] = Field(default_factory=list)
