import datetime as dt
from typing import List, Optional

from pydantic import BaseModel

from app.schemas.analytics_schemas import DailyLeadCount


class FunnelStats(BaseModel):
    # "Обработано сообщений" isn't included here: messages the keyword
    # pre-filter rejects are never persisted at all (by design, to avoid
    # a DB write per irrelevant message — see KeywordFilter), so there is
    # no real per-profile count of them to show. Candidates is therefore
    # the funnel's true entry point: every Lead row means the message
    # passed the keyword filter and reached AI analysis.
    candidates: int
    leads: int
    hot_leads: int


class SourceStat(BaseModel):
    source_id: int
    source_name: str
    lead_count: int


class NicheStat(BaseModel):
    niche: str
    lead_count: int


class ProfileAnalytics(BaseModel):
    period: str
    funnel: FunnelStats
    avg_match_score: float
    avg_budget: Optional[float] = None
    budget_currency: Optional[str] = None
    top_sources: List[SourceStat]
    top_niches: List[NicheStat]
    leads_by_day: List[DailyLeadCount]
