"""ProfileAnalyticsService: per-SearchProfile funnel + breakdown stats
(Этап 10). Companion to LeadStatsService (which only does the flat
overview + daily series) — this adds the funnel, top sources/niches, and
average Match Score/budget the "Мои поиски" / analytics page needs.
"""
import datetime as dt
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source


@dataclass(frozen=True)
class FunnelResult:
    candidates: int
    leads: int
    hot_leads: int


@dataclass(frozen=True)
class SourceStatResult:
    source_id: int
    source_name: str
    lead_count: int


@dataclass(frozen=True)
class NicheStatResult:
    niche: str
    lead_count: int


@dataclass(frozen=True)
class ProfileAnalyticsResult:
    funnel: FunnelResult
    avg_match_score: float
    avg_budget: Optional[float]
    budget_currency: Optional[str]
    top_sources: List[SourceStatResult] = field(default_factory=list)
    top_niches: List[NicheStatResult] = field(default_factory=list)


class ProfileAnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_stmt(self, search_profile_id: int, date_from: Optional[dt.datetime]):
        stmt = select(Lead).where(Lead.search_profile_id == search_profile_id)
        if date_from is not None:
            stmt = stmt.where(Lead.created_at >= date_from)
        return stmt

    async def get_analytics(
        self,
        search_profile_id: int,
        notification_threshold: int,
        date_from: Optional[dt.datetime] = None,
        top_n: int = 5,
    ) -> ProfileAnalyticsResult:
        base_filter = [Lead.search_profile_id == search_profile_id]
        if date_from is not None:
            base_filter.append(Lead.created_at >= date_from)

        candidates = await self.session.scalar(
            select(func.count(Lead.id)).where(*base_filter)
        )
        leads = await self.session.scalar(
            select(func.count(Lead.id)).where(*base_filter, Lead.is_lead.is_(True))
        )
        hot_leads = await self.session.scalar(
            select(func.count(Lead.id)).where(
                *base_filter, Lead.lead_score >= notification_threshold
            )
        )

        avg_score = await self.session.scalar(
            select(func.avg(Lead.lead_score)).where(*base_filter)
        )
        avg_budget = await self.session.scalar(
            select(func.avg((Lead.budget_min + Lead.budget_max) / 2.0)).where(
                *base_filter, Lead.budget_min.isnot(None), Lead.budget_max.isnot(None)
            )
        )
        currency_row = await self.session.execute(
            select(Lead.currency)
            .where(*base_filter, Lead.currency.isnot(None))
            .group_by(Lead.currency)
            .order_by(func.count(Lead.id).desc())
            .limit(1)
        )
        budget_currency = currency_row.scalar_one_or_none()

        source_stmt = (
            select(Source.id, Source.name, func.count(Lead.id))
            .join(RawItem, Lead.raw_item_id == RawItem.id)
            .join(Source, RawItem.source_id == Source.id)
            .where(*base_filter)
            .group_by(Source.id, Source.name)
            .order_by(func.count(Lead.id).desc())
            .limit(top_n)
        )
        source_rows = await self.session.execute(source_stmt)
        top_sources = [
            SourceStatResult(source_id=sid, source_name=name, lead_count=count)
            for sid, name, count in source_rows.all()
        ]

        niche_stmt = (
            select(Lead.business_niche, func.count(Lead.id))
            .where(*base_filter, Lead.business_niche.isnot(None))
            .group_by(Lead.business_niche)
            .order_by(func.count(Lead.id).desc())
            .limit(top_n)
        )
        niche_rows = await self.session.execute(niche_stmt)
        top_niches = [
            NicheStatResult(niche=niche, lead_count=count) for niche, count in niche_rows.all()
        ]

        return ProfileAnalyticsResult(
            funnel=FunnelResult(
                candidates=candidates or 0, leads=leads or 0, hot_leads=hot_leads or 0
            ),
            avg_match_score=round(float(avg_score), 1) if avg_score is not None else 0.0,
            avg_budget=round(float(avg_budget), 2) if avg_budget is not None else None,
            budget_currency=budget_currency,
            top_sources=top_sources,
            top_niches=top_niches,
        )
