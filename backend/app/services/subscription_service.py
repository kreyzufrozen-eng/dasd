"""Этап 11 (see IMPLEMENTATION_PLAN.md §10): architecture-only
subscriptions. No payment provider exists — every user is on the single
free plan, auto-assigned at registration (see ensure_free_subscription,
called from app/api/auth.py register()). This module also builds the
read-only usage summary the "your plan/usage" panel displays; nothing
here enforces the limits it shows yet.
"""
import datetime as dt
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_profile import SearchProfile
from app.models.subscription_plan import SubscriptionPlan
from app.repositories.subscription_plan_repository import SubscriptionPlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.usage_counter_repository import UsageCounterRepository

FREE_PLAN_NAME = "Free"

# Fallback used only if the 0007 migration's seed row is somehow missing
# (e.g. a test DB built straight from models rather than via Alembic) —
# keeps ensure_free_subscription usable without requiring migrations to
# have run, mirroring how ensure_keywords_seeded tolerates an empty catalog.
_FREE_PLAN_DEFAULTS = dict(
    max_search_profiles=3,
    max_sources_per_profile=10,
    max_ai_analyses_per_month=1000,
    price=None,
    currency="RUB",
)


def _current_period_start(now: Optional[dt.datetime] = None) -> dt.datetime:
    now = now or dt.datetime.now(dt.timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


async def _get_or_create_free_plan(session: AsyncSession) -> SubscriptionPlan:
    plan_repo = SubscriptionPlanRepository(session)
    plan = await plan_repo.get_by_name(FREE_PLAN_NAME)
    if plan is None:
        plan = await plan_repo.create(name=FREE_PLAN_NAME, **_FREE_PLAN_DEFAULTS)
    return plan


async def ensure_free_subscription(session: AsyncSession, user_id: int) -> None:
    """Idempotent — safe to call on every registration and, defensively,
    from anywhere that reads a user's plan (a user created before this
    Этап shipped won't have a row until the 0007 backfill/this runs)."""
    sub_repo = SubscriptionRepository(session)
    existing = await sub_repo.get_for_user(user_id)
    if existing is not None:
        return

    plan = await _get_or_create_free_plan(session)
    await sub_repo.create(
        user_id=user_id,
        plan_id=plan.id,
        status="active",
        current_period_start=dt.datetime.now(dt.timezone.utc),
    )


@dataclass(frozen=True)
class UsageSummary:
    plan_name: str
    max_search_profiles: int
    max_sources_per_profile: int
    max_ai_analyses_per_month: int
    price: Optional[float]
    currency: str
    search_profiles_used: int
    ai_analyses_used_this_period: int
    period_start: dt.datetime


async def get_usage_summary(session: AsyncSession, user_id: int) -> UsageSummary:
    await ensure_free_subscription(session, user_id)
    sub_repo = SubscriptionRepository(session)
    subscription = await sub_repo.get_for_user(user_id)
    plan = subscription.plan

    profile_count = await session.scalar(
        select(func.count(SearchProfile.id)).where(SearchProfile.user_id == user_id)
    )

    period_start = _current_period_start()
    usage_repo = UsageCounterRepository(session)
    counter = await usage_repo.get_for_period(user_id, period_start)

    return UsageSummary(
        plan_name=plan.name,
        max_search_profiles=plan.max_search_profiles,
        max_sources_per_profile=plan.max_sources_per_profile,
        max_ai_analyses_per_month=plan.max_ai_analyses_per_month,
        price=plan.price,
        currency=plan.currency,
        search_profiles_used=profile_count or 0,
        ai_analyses_used_this_period=counter.ai_analyses_count if counter else 0,
        period_start=period_start,
    )
