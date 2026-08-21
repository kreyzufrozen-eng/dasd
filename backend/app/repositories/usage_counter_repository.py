import datetime as dt
from typing import Optional

from sqlalchemy import select

from app.models.usage_counter import UsageCounter
from app.repositories.base import BaseRepository


class UsageCounterRepository(BaseRepository[UsageCounter]):
    model = UsageCounter

    async def get_for_period(self, user_id: int, period_start: dt.datetime) -> Optional[UsageCounter]:
        stmt = select(UsageCounter).where(
            UsageCounter.user_id == user_id, UsageCounter.period_start == period_start
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
