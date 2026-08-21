"""LeadStatsService: shared query logic behind /stats (bot, Stage 8) and
/api/analytics/overview (REST API, Stage 9) — written once here so those
two surfaces never drift out of sync (per "не дублируй код").
"""
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LeadStatus
from app.models.lead import Lead


@dataclass(frozen=True)
class LeadStatsOverview:
    total: int
    today: int
    hot: int
    converted: int


@dataclass(frozen=True)
class DailyCount:
    date: dt.date
    count: int


class LeadStatsService:
    def __init__(
        self,
        session: AsyncSession,
        notification_threshold: int = 60,
        search_profile_id: Optional[int] = None,
    ) -> None:
        self.session = session
        self.notification_threshold = notification_threshold
        # None = unscoped (bot /stats, which is still single-profile-only —
        # see PROJECT_AUDIT.md). /api/analytics/overview always passes the
        # caller's own profile so one tenant's stats never leak into
        # another's dashboard.
        self.search_profile_id = search_profile_id

    async def _count(self, stmt) -> int:
        if self.search_profile_id is not None:
            stmt = stmt.where(Lead.search_profile_id == self.search_profile_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_overview(self) -> LeadStatsOverview:
        now = dt.datetime.now(dt.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total = await self._count(select(func.count(Lead.id)))
        today = await self._count(
            select(func.count(Lead.id)).where(Lead.created_at >= today_start)
        )
        hot = await self._count(
            select(func.count(Lead.id)).where(Lead.lead_score >= self.notification_threshold)
        )
        converted = await self._count(
            select(func.count(Lead.id)).where(Lead.status == LeadStatus.CONVERTED.value)
        )

        return LeadStatsOverview(total=total, today=today, hot=hot, converted=converted)

    async def get_daily_counts(self, days: int) -> List[DailyCount]:
        """Lead counts per day for the last `days` days (including today),
        zero-filled for days with no leads. `func.date()` compiles to a
        plain `date(...)` call on both SQLite and Postgres, so this query
        is portable between the test suite and production."""
        now = dt.datetime.now(dt.timezone.utc)
        today = now.date()
        start = today - dt.timedelta(days=days - 1)
        start_dt = dt.datetime.combine(start, dt.time.min, tzinfo=dt.timezone.utc)

        stmt = select(func.date(Lead.created_at), func.count(Lead.id)).where(
            Lead.created_at >= start_dt
        )
        if self.search_profile_id is not None:
            stmt = stmt.where(Lead.search_profile_id == self.search_profile_id)
        stmt = stmt.group_by(func.date(Lead.created_at))
        result = await self.session.execute(stmt)
        counts_by_day = {str(day): count for day, count in result.all()}

        return [
            DailyCount(date=start + dt.timedelta(days=i), count=counts_by_day.get(str(start + dt.timedelta(days=i)), 0))
            for i in range(days)
        ]
