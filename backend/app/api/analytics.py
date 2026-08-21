"""REST API: /api/analytics/overview — scoped to the authenticated user's
SearchProfile, same isolation model as /api/leads (see app/api/leads.py)."""
import datetime as dt
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import resolve_profile_id
from app.core.config import Settings, get_settings
from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.schemas.analytics_schemas import AnalyticsOverview, DailyLeadCount
from app.services.lead_stats import LeadStatsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
async def analytics_overview(
    search_profile_id: Optional[int] = Query(
        default=None, description="Defaults to the caller's first profile if omitted"
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> AnalyticsOverview:
    profile_id = await resolve_profile_id(db, user, search_profile_id)
    if profile_id is None:
        # No SearchProfile yet (onboarding not completed) — all-zeros,
        # same graceful empty state as an empty leads list. Must NOT fall
        # through to LeadStatsService with search_profile_id=None, since
        # that sentinel means "unscoped" there (used by the bot) — for a
        # profile-less user that would leak every tenant's aggregate stats.
        zero_7 = [DailyLeadCount(date=dt.date.today() - dt.timedelta(days=i), count=0) for i in range(7)][::-1]
        zero_30 = [DailyLeadCount(date=dt.date.today() - dt.timedelta(days=i), count=0) for i in range(30)][::-1]
        return AnalyticsOverview(
            total_leads=0,
            today_leads=0,
            hot_leads=0,
            converted_leads=0,
            leads_last_7_days=zero_7,
            leads_last_30_days=zero_30,
        )

    stats_service = LeadStatsService(
        db, notification_threshold=settings.NOTIFICATION_THRESHOLD, search_profile_id=profile_id
    )

    overview = await stats_service.get_overview()
    last_7 = await stats_service.get_daily_counts(7)
    last_30 = await stats_service.get_daily_counts(30)

    return AnalyticsOverview(
        total_leads=overview.total,
        today_leads=overview.today,
        hot_leads=overview.hot,
        converted_leads=overview.converted,
        leads_last_7_days=[DailyLeadCount(date=d.date, count=d.count) for d in last_7],
        leads_last_30_days=[DailyLeadCount(date=d.date, count=d.count) for d in last_30],
    )
