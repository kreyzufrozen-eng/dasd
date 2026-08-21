import datetime as dt
from typing import List

from pydantic import BaseModel


class DailyLeadCount(BaseModel):
    date: dt.date
    count: int


class AnalyticsOverview(BaseModel):
    total_leads: int
    today_leads: int
    hot_leads: int
    converted_leads: int
    leads_last_7_days: List[DailyLeadCount]
    leads_last_30_days: List[DailyLeadCount]
