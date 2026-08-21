from typing import Optional, Sequence

from sqlalchemy import select

from app.models.subscription_plan import SubscriptionPlan
from app.repositories.base import BaseRepository


class SubscriptionPlanRepository(BaseRepository[SubscriptionPlan]):
    model = SubscriptionPlan

    async def get_by_name(self, name: str) -> Optional[SubscriptionPlan]:
        stmt = select(SubscriptionPlan).where(SubscriptionPlan.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[SubscriptionPlan]:
        stmt = select(SubscriptionPlan).order_by(SubscriptionPlan.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
