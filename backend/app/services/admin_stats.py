"""AdminStatsService: system-wide (not per-user-scoped) counts for the
admin panel — analogous to LeadStatsService, but deliberately unscoped
since only admins can reach it (see app/api/admin.py).
"""
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.audit_log import AuditLog
from app.models.keyword import Keyword
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.search_profile import SearchProfile
from app.models.search_profile_source import SearchProfileSource
from app.models.source import Source
from app.models.user import User

# Both actions mean "the user actually opened a session" — email/password
# login logs "login", either Telegram purpose (site login or later linking)
# logs "telegram_connect" (see app/api/telegram_auth.py). Register doesn't
# count on its own: it's covered by created_at already shown separately.
LOGIN_ACTIONS = ("login", "telegram_connect")


@dataclass(frozen=True)
class AdminOverviewStats:
    total_users: int
    total_search_profiles: int
    total_sources: int
    active_sources: int
    total_keywords: int
    total_raw_items: int
    total_leads: int
    leads_today: int


@dataclass(frozen=True)
class AdminUserStats:
    user: User
    search_profile_count: int
    lead_count: int
    last_login_at: Optional[dt.datetime] = None


class AdminStatsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _count(self, stmt) -> int:
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_overview(self) -> AdminOverviewStats:
        now = dt.datetime.now(dt.timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        return AdminOverviewStats(
            total_users=await self._count(select(func.count(User.id))),
            total_search_profiles=await self._count(select(func.count(SearchProfile.id))),
            total_sources=await self._count(select(func.count(Source.id))),
            active_sources=await self._count(
                select(func.count(Source.id)).where(Source.is_active.is_(True))
            ),
            total_keywords=await self._count(select(func.count(Keyword.id))),
            total_raw_items=await self._count(select(func.count(RawItem.id))),
            total_leads=await self._count(select(func.count(Lead.id))),
            leads_today=await self._count(
                select(func.count(Lead.id)).where(Lead.created_at >= today_start)
            ),
        )

    async def get_users_with_stats(self) -> List[AdminUserStats]:
        """Every user, with their SearchProfile count and total Lead count
        across all their profiles. Two grouped queries rather than one big
        join — a user with N profiles and M leads would otherwise get
        double-counted by a single Lead-joined-to-User query."""
        users_result = await self.session.execute(select(User).order_by(User.created_at.asc()))
        users = users_result.scalars().all()

        profile_counts_result = await self.session.execute(
            select(SearchProfile.user_id, func.count(SearchProfile.id)).group_by(
                SearchProfile.user_id
            )
        )
        profile_counts = dict(profile_counts_result.all())

        lead_counts_result = await self.session.execute(
            select(SearchProfile.user_id, func.count(Lead.id))
            .join(Lead, Lead.search_profile_id == SearchProfile.id)
            .group_by(SearchProfile.user_id)
        )
        lead_counts = dict(lead_counts_result.all())

        last_login_result = await self.session.execute(
            select(AuditLog.user_id, func.max(AuditLog.created_at))
            .where(AuditLog.action.in_(LOGIN_ACTIONS))
            .group_by(AuditLog.user_id)
        )
        last_login_by_user = dict(last_login_result.all())

        return [
            AdminUserStats(
                user=user,
                search_profile_count=profile_counts.get(user.id, 0),
                lead_count=lead_counts.get(user.id, 0),
                last_login_at=last_login_by_user.get(user.id),
            )
            for user in users
        ]

    async def get_user_profiles_detailed(self, user_id: int) -> List[SearchProfile]:
        """Every SearchProfile for one user, with sources (+ their catalog
        Source row) and keywords eager-loaded — what the admin "Профиль"
        detail view renders. See app/api/admin.py for how this gets
        flattened into AdminSearchProfileDetail (deliberately not done via
        Pydantic from_attributes here: the response shape renames/derives
        fields — e.g. source_links[i].source.name -> sources[i].name,
        is_custom from added_by_user_id — that from_attributes can't do on
        its own without a matching model_validator)."""
        stmt = (
            select(SearchProfile)
            .where(SearchProfile.user_id == user_id)
            .options(
                selectinload(SearchProfile.source_links).selectinload(SearchProfileSource.source),
                selectinload(SearchProfile.keyword_links),
            )
            .order_by(SearchProfile.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
