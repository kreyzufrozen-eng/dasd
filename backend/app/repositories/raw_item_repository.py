import datetime as dt
from typing import Optional, Sequence

from sqlalchemy import select

from app.models.raw_item import RawItem
from app.repositories.base import BaseRepository


class RawItemRepository(BaseRepository[RawItem]):
    model = RawItem

    async def get_by_source_and_external_id(
        self, source_id: int, external_id: str
    ) -> Optional[RawItem]:
        """Dedup check #1: same source + same external message id."""
        stmt = select(RawItem).where(
            RawItem.source_id == source_id, RawItem.external_id == external_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_content_hash(self, content_hash: str) -> Optional[RawItem]:
        """Dedup check #2: identical normalized text content, any source."""
        stmt = select(RawItem).where(RawItem.content_hash == content_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_without_lead(
        self, search_profile_id: int, limit: int = 100, max_age_days: Optional[int] = None
    ) -> Sequence[RawItem]:
        """RawItems `search_profile_id` hasn't produced a Lead for yet
        (queue for Stage 7's Filter -> AI -> Score step).

        Scoped per profile (Stage 1: Lead is N:1 with RawItem, see
        models/lead.py) — a RawItem already analyzed for one profile can
        still be pending for another.

        Newest first: a fresh lead is worth more than an old one, and with
        a large backlog (e.g. right after adding many new sources) newest-
        first means the pipeline surfaces current opportunities immediately
        instead of spending hours/days working through historical backlog
        before it reaches anything recent.

        max_age_days, if given, drops anything older outright — leads go
        stale fast, so there's no value in ever running an old item through
        AI analysis, and skipping it here keeps the backlog from crowding
        out genuinely new items on ties within the same collection batch.
        """
        from app.models.lead import Lead  # local import avoids circular import

        stmt = (
            select(RawItem)
            .outerjoin(
                Lead,
                (Lead.raw_item_id == RawItem.id) & (Lead.search_profile_id == search_profile_id),
            )
            .where(Lead.id.is_(None))
        )
        if max_age_days is not None:
            cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=max_age_days)
            stmt = stmt.where(RawItem.created_at >= cutoff)
        stmt = stmt.order_by(RawItem.created_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
