from typing import Optional, Sequence

from sqlalchemy import select

from app.models.source import Source
from app.repositories.base import BaseRepository


class SourceRepository(BaseRepository[Source]):
    model = Source

    async def get_by_type_and_identifier(
        self, type_: str, external_identifier: str
    ) -> Optional[Source]:
        stmt = select(Source).where(
            Source.type == type_, Source.external_identifier == external_identifier
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self, type_: Optional[str] = None) -> Sequence[Source]:
        stmt = select(Source).where(Source.is_active.is_(True))
        if type_:
            stmt = stmt.where(Source.type == type_)
        result = await self.session.execute(stmt)
        return result.scalars().all()
