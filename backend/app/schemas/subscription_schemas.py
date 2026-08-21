import datetime as dt
from typing import Optional

from pydantic import BaseModel


class UsageSummaryRead(BaseModel):
    plan_name: str
    max_search_profiles: int
    max_sources_per_profile: int
    max_ai_analyses_per_month: int
    price: Optional[float] = None
    currency: str
    search_profiles_used: int
    ai_analyses_used_this_period: int
    period_start: dt.datetime
