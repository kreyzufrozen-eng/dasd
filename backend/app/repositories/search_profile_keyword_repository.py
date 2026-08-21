from typing import Optional, Sequence

from sqlalchemy import select

from app.models.search_profile_keyword import SearchProfileKeyword
from app.repositories.base import BaseRepository


class SearchProfileKeywordRepository(BaseRepository[SearchProfileKeyword]):
    model = SearchProfileKeyword

    async def list_for_profile(
        self, search_profile_id: int, category: Optional[str] = None
    ) -> Sequence[SearchProfileKeyword]:
        stmt = select(SearchProfileKeyword).where(
            SearchProfileKeyword.search_profile_id == search_profile_id
        )
        if category:
            stmt = stmt.where(SearchProfileKeyword.category == category)
        stmt = stmt.order_by(SearchProfileKeyword.created_at.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_enabled_for_profile(
        self, search_profile_id: int
    ) -> Sequence[SearchProfileKeyword]:
        """What the pipeline's per-profile KeywordFilter is built from."""
        stmt = select(SearchProfileKeyword).where(
            SearchProfileKeyword.search_profile_id == search_profile_id,
            SearchProfileKeyword.enabled.is_(True),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_text(
        self, search_profile_id: int, text: str
    ) -> Optional[SearchProfileKeyword]:
        stmt = select(SearchProfileKeyword).where(
            SearchProfileKeyword.search_profile_id == search_profile_id,
            SearchProfileKeyword.text == text,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def bulk_create(
        self, search_profile_id: int, entries: list[dict]
    ) -> list[SearchProfileKeyword]:
        """entries: [{"text", "category", "weight"?, "keyword_id"?}, ...] —
        used by onboarding's AI-generated starter keyword set and the
        "Сгенерировать ключевые слова" button, both of which produce many
        rows in one call."""
        created = []
        for entry in entries:
            obj = SearchProfileKeyword(
                search_profile_id=search_profile_id,
                keyword_id=entry.get("keyword_id"),
                text=entry["text"],
                category=entry["category"],
                weight=entry.get("weight", 1.0),
                enabled=entry.get("enabled", True),
            )
            self.session.add(obj)
            created.append(obj)
        await self.session.flush()
        for obj in created:
            await self.session.refresh(obj)
        return created
