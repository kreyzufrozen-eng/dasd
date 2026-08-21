from typing import Sequence

from sqlalchemy import select

from app.models.lead_feedback import LeadFeedback
from app.repositories.base import BaseRepository


class LeadFeedbackRepository(BaseRepository[LeadFeedback]):
    model = LeadFeedback

    async def list_for_lead(self, lead_id: int) -> Sequence[LeadFeedback]:
        stmt = select(LeadFeedback).where(LeadFeedback.lead_id == lead_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()
