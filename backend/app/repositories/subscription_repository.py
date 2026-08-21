from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.subscription import Subscription
from app.repositories.base import BaseRepository


class SubscriptionRepository(BaseRepository[Subscription]):
    model = Subscription

    async def get_for_user(self, user_id: int) -> Optional[Subscription]:
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .options(joinedload(Subscription.plan))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
