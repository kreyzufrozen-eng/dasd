from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.search_profile_source import SearchProfileSource
from app.models.source import Source
from app.repositories.base import BaseRepository


class SearchProfileSourceRepository(BaseRepository[SearchProfileSource]):
    model = SearchProfileSource

    async def list_for_profile(self, search_profile_id: int) -> Sequence[SearchProfileSource]:
        stmt = (
            select(SearchProfileSource)
            .where(SearchProfileSource.search_profile_id == search_profile_id)
            .options(selectinload(SearchProfileSource.source))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_source(self, link_id: int) -> Optional[SearchProfileSource]:
        """Like get(), but eager-loads `.source` — plain session.get() does
        not, and accessing a lazy relationship outside a sync context
        raises MissingGreenlet under the async engine."""
        stmt = (
            select(SearchProfileSource)
            .where(SearchProfileSource.id == link_id)
            .options(selectinload(SearchProfileSource.source))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_link(
        self, search_profile_id: int, source_id: int
    ) -> Optional[SearchProfileSource]:
        stmt = select(SearchProfileSource).where(
            SearchProfileSource.search_profile_id == search_profile_id,
            SearchProfileSource.source_id == source_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_enabled_source_ids_for_profile(self, search_profile_id: int) -> set[int]:
        """Fast path for the pipeline: just the ids, no Source join."""
        stmt = select(SearchProfileSource.source_id).where(
            SearchProfileSource.search_profile_id == search_profile_id,
            SearchProfileSource.enabled.is_(True),
        )
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def bulk_attach(
        self, search_profile_id: int, source_ids: list[int]
    ) -> int:
        """One query to find what's already linked, one INSERT for the
        rest — used by onboarding's launch step, which can otherwise be
        asked to attach hundreds of sources at once (the "наша база
        источников" bulk-select — see frontend onboarding page). N
        sequential single-attach calls took 1-2+ minutes over the network
        for a few hundred sources; this is one round trip.

        Returns how many *new* links were created (already-linked ids are
        silently skipped, not an error — this mirrors attach_profile_source's
        own "idempotent re-attach" behavior)."""
        if not source_ids:
            return 0

        existing_stmt = select(SearchProfileSource.source_id).where(
            SearchProfileSource.search_profile_id == search_profile_id,
            SearchProfileSource.source_id.in_(source_ids),
        )
        existing_ids = set((await self.session.execute(existing_stmt)).scalars().all())

        # Silently drop any id that isn't a real Source row — same
        # "one bad id shouldn't fail the batch" behavior the old
        # per-item attach loop had via its try/except.
        valid_stmt = select(Source.id).where(Source.id.in_(source_ids))
        valid_ids = set((await self.session.execute(valid_stmt)).scalars().all())

        to_create = [sid for sid in set(source_ids) if sid not in existing_ids and sid in valid_ids]
        for source_id in to_create:
            self.session.add(
                SearchProfileSource(
                    search_profile_id=search_profile_id, source_id=source_id, enabled=True
                )
            )
        if to_create:
            await self.session.flush()
        return len(to_create)
