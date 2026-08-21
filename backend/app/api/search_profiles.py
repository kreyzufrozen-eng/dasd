"""REST API: /api/search-profiles — scoped to the authenticated user.

A user can only ever see/modify their own profiles: get_or_404_owned
below checks user_id after the lookup and raises the same 404 a
nonexistent id would (not 403) so a profile id belonging to someone else
can't be distinguished from one that doesn't exist at all.
"""
import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.exceptions import AIProviderError, AIResponseValidationError
from app.ai.factory import get_ai_provider
from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.rate_limit import rate_limit
from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.search_profile import SearchProfile
from app.models.user import User
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.profile_analytics import (
    FunnelStats,
    NicheStat,
    ProfileAnalytics,
    SourceStat,
)
from app.schemas.profile_draft import ProfileDraft, ProfileDraftRequest
from app.schemas.search_profile_schemas import (
    SearchProfileCreate,
    SearchProfileRead,
    SearchProfileUpdate,
)
from app.schemas.analytics_schemas import DailyLeadCount
from app.services.lead_stats import LeadStatsService
from app.services.profile_analytics import ProfileAnalyticsService
from app.services.profile_keyword_seeder import ensure_keywords_seeded

logger = get_logger(__name__)

router = APIRouter(prefix="/api/search-profiles", tags=["search-profiles"])


async def _get_owned_or_404(
    repo: SearchProfileRepository, profile_id: int, user_id: int
) -> SearchProfile:
    profile = await repo.get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise NotFoundError("Search profile not found")
    return profile


@router.get("", response_model=list[SearchProfileRead])
async def list_search_profiles(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db_session)
) -> list[SearchProfile]:
    repo = SearchProfileRepository(db)
    return list(await repo.list_for_user(user.id))


@router.post("", response_model=SearchProfileRead, status_code=201)
async def create_search_profile(
    payload: SearchProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfile:
    data = payload.model_dump()
    keywords = data.pop("keywords")

    repo = SearchProfileRepository(db)
    profile = await repo.create(user_id=user.id, **data)

    if keywords:
        # Onboarding's own AI-generated (and possibly user-edited) set —
        # use it as-is instead of the generic global-catalog seed.
        await SearchProfileKeywordRepository(db).bulk_create(profile.id, keywords)
    else:
        # A profile with zero keywords never matches anything in the
        # pipeline's pre-filter — seed from the global catalog so a
        # profile created outside onboarding (e.g. directly via this
        # endpoint) still works.
        await ensure_keywords_seeded(db, profile.id)

    await db.commit()
    return profile


@router.post(
    "/generate-draft",
    response_model=ProfileDraft,
    dependencies=[Depends(rate_limit("generate_profile_draft", max_attempts=15, window_seconds=600))],
)
async def generate_profile_draft(
    payload: ProfileDraftRequest,
    _user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> ProfileDraft:
    """Onboarding step 1: no DB write — just turns the user's plain-text
    description into a structured, still-editable draft (see
    app/schemas/profile_draft.py). The wizard's later "🚀 Запустить поиск"
    step is what actually calls POST /api/search-profiles with whatever
    the user kept/edited from this draft."""
    try:
        ai_provider = get_ai_provider(settings)
    except ValueError as exc:
        logger.error("Cannot build AI provider for profile draft: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider is not configured",
        ) from exc

    try:
        return await ai_provider.generate_profile_draft(payload.description)
    except (AIProviderError, AIResponseValidationError) as exc:
        logger.error("Profile draft generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not generate a profile draft right now — please try again",
        ) from exc


@router.get("/{profile_id}", response_model=SearchProfileRead)
async def get_search_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfile:
    repo = SearchProfileRepository(db)
    return await _get_owned_or_404(repo, profile_id, user.id)


_PERIOD_DAYS = {"today": 0, "7d": 7, "30d": 30}


@router.get("/{profile_id}/analytics", response_model=ProfileAnalytics)
async def get_profile_analytics(
    profile_id: int,
    period: str = Query("7d", pattern="^(today|7d|30d|all)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ProfileAnalytics:
    repo = SearchProfileRepository(db)
    profile = await _get_owned_or_404(repo, profile_id, user.id)

    date_from = None
    if period != "all":
        days = _PERIOD_DAYS[period]
        now = dt.datetime.now(dt.timezone.utc)
        date_from = (
            now.replace(hour=0, minute=0, second=0, microsecond=0)
            if days == 0
            else now - dt.timedelta(days=days)
        )

    result = await ProfileAnalyticsService(db).get_analytics(
        profile_id, profile.notification_threshold, date_from=date_from
    )

    series_days = 7 if period in ("today", "7d") else 30
    stats_service = LeadStatsService(db, search_profile_id=profile_id)
    daily = await stats_service.get_daily_counts(series_days)

    return ProfileAnalytics(
        period=period,
        funnel=FunnelStats(
            candidates=result.funnel.candidates,
            leads=result.funnel.leads,
            hot_leads=result.funnel.hot_leads,
        ),
        avg_match_score=result.avg_match_score,
        avg_budget=result.avg_budget,
        budget_currency=result.budget_currency,
        top_sources=[
            SourceStat(source_id=s.source_id, source_name=s.source_name, lead_count=s.lead_count)
            for s in result.top_sources
        ],
        top_niches=[NicheStat(niche=n.niche, lead_count=n.lead_count) for n in result.top_niches],
        leads_by_day=[DailyLeadCount(date=d.date, count=d.count) for d in daily],
    )


@router.patch("/{profile_id}", response_model=SearchProfileRead)
async def update_search_profile(
    profile_id: int,
    payload: SearchProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfile:
    repo = SearchProfileRepository(db)
    profile = await _get_owned_or_404(repo, profile_id, user.id)

    update_data = payload.model_dump(exclude_unset=True)
    updated = await repo.update(profile, **update_data)
    await db.commit()
    return updated


@router.delete("/{profile_id}", status_code=204)
async def delete_search_profile(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    repo = SearchProfileRepository(db)
    profile = await _get_owned_or_404(repo, profile_id, user.id)

    await repo.delete(profile)
    await db.commit()
