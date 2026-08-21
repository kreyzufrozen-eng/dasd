from typing import Optional, Sequence

from sqlalchemy import select

from app.models.search_profile import SearchProfile
from app.repositories.base import BaseRepository


class SearchProfileRepository(BaseRepository[SearchProfile]):
    model = SearchProfile

    async def list_for_user(self, user_id: int) -> Sequence[SearchProfile]:
        stmt = select(SearchProfile).where(SearchProfile.user_id == user_id).order_by(
            SearchProfile.created_at.asc()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_ids_for_user(self, user_id: int) -> set[int]:
        """Every profile id this user owns — used by endpoints that look up
        a Lead/resource by id first and then need to check it belongs to
        *any* of the caller's profiles (multi-profile-aware ownership
        check), not just their first one."""
        profiles = await self.list_for_user(user_id)
        return {p.id for p in profiles}

    async def get_first_id_for_user(self, user_id: int) -> Optional[int]:
        """A user can have several profiles (Этап 2+) — this is just the
        *default* one an endpoint falls back to when the caller didn't
        explicitly pass search_profile_id (see app/api/deps.py
        resolve_profile_id). Not a statement that a user has only one."""
        profiles = await self.list_for_user(user_id)
        return profiles[0].id if profiles else None

    async def list_active(self) -> Sequence[SearchProfile]:
        """Every active profile system-wide — what the pipeline fans out
        across (Этап 3). Not scoped to one user: the worker processes all
        tenants' profiles in a single pass."""
        stmt = select(SearchProfile).where(SearchProfile.is_active.is_(True)).order_by(
            SearchProfile.created_at.asc()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_primary(self) -> Optional[SearchProfile]:
        """The oldest active profile system-wide.

        Since Этап 3 the pipeline itself fans out across list_active()
        instead of using this — get_primary() is now only what the
        Telegram bot commands (/leads, /hot, /stats) fall back to, since
        the bot has no per-user login of its own yet (IsOwner just checks
        NOTIFICATION_CHAT_ID against a single owner). See
        IMPLEMENTATION_PLAN.md for the "one Telegram bot chat = one
        recipient" limitation this reflects.
        """
        stmt = (
            select(SearchProfile)
            .where(SearchProfile.is_active.is_(True))
            .order_by(SearchProfile.created_at.asc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
