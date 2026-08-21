import datetime as dt
from typing import Optional, Sequence

from sqlalchemy import func, select

from app.models.lead import Lead
from app.repositories.base import BaseRepository


class LeadRepository(BaseRepository[Lead]):
    model = Lead

    async def get_by_raw_item_and_profile(
        self, raw_item_id: int, search_profile_id: int
    ) -> Optional[Lead]:
        """A RawItem can now have a Lead per SearchProfile — this is the
        dedup check for "has THIS profile already seen this item", not
        "has anyone"."""
        stmt = select(Lead).where(
            Lead.raw_item_id == raw_item_id, Lead.search_profile_id == search_profile_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search(
        self,
        search_profile_id: int,
        score_min: Optional[int] = None,
        score_max: Optional[int] = None,
        intent_score_min: Optional[int] = None,
        status: Optional[str] = None,
        source_id: Optional[int] = None,
        lead_type: Optional[str] = None,
        is_lead: Optional[bool] = None,
        date_from: Optional[dt.datetime] = None,
        date_to: Optional[dt.datetime] = None,
        sort: str = "newest",
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Lead]:
        from app.models.raw_item import RawItem  # local import avoids circular import

        stmt = select(Lead).where(Lead.search_profile_id == search_profile_id)
        if source_id is not None:
            stmt = stmt.join(RawItem, Lead.raw_item_id == RawItem.id).where(
                RawItem.source_id == source_id
            )
        if score_min is not None:
            stmt = stmt.where(Lead.lead_score >= score_min)
        if score_max is not None:
            stmt = stmt.where(Lead.lead_score <= score_max)
        if intent_score_min is not None:
            stmt = stmt.where(Lead.intent_score >= intent_score_min)
        if status is not None:
            stmt = stmt.where(Lead.status == status)
        if lead_type is not None:
            stmt = stmt.where(Lead.lead_type == lead_type)
        if is_lead is not None:
            stmt = stmt.where(Lead.is_lead == is_lead)
        if date_from is not None:
            stmt = stmt.where(Lead.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Lead.created_at <= date_to)

        order_columns = {
            "score": Lead.lead_score.desc(),
            "intent": Lead.intent_score.desc(),
            "newest": Lead.created_at.desc(),
        }
        stmt = stmt.order_by(order_columns.get(sort, order_columns["newest"]))
        stmt = stmt.offset(offset).limit(limit)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_for_source(self, source_id: int) -> int:
        from app.models.raw_item import RawItem  # local import avoids circular import

        stmt = (
            select(func.count(Lead.id))
            .join(RawItem, Lead.raw_item_id == RawItem.id)
            .where(RawItem.source_id == source_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
