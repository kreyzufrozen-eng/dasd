from typing import Optional, Sequence

from sqlalchemy import select

from app.models.keyword import Keyword
from app.repositories.base import BaseRepository


class KeywordRepository(BaseRepository[Keyword]):
    model = Keyword

    async def list_active(self, category: Optional[str] = None) -> Sequence[Keyword]:
        stmt = select(Keyword).where(Keyword.is_active.is_(True))
        if category:
            stmt = stmt.where(Keyword.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self, category: Optional[str] = None) -> Sequence[Keyword]:
        """Includes inactive keywords too — for the admin/keywords management
        page, unlike list_active() which the pre-filter builder uses."""
        stmt = select(Keyword)
        if category:
            stmt = stmt.where(Keyword.category == category)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_keyword_and_category(
        self, keyword: str, category: str
    ) -> Optional[Keyword]:
        stmt = select(Keyword).where(
            Keyword.keyword == keyword, Keyword.category == category
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
