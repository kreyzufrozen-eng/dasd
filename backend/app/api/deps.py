"""Shared FastAPI dependencies for the API layer."""
from typing import TYPE_CHECKING, Optional, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.repositories.base import BaseRepository
from app.repositories.search_profile_repository import SearchProfileRepository

if TYPE_CHECKING:
    from app.models.user import User

ModelT = TypeVar("ModelT")


async def get_or_404(repo: BaseRepository, id_: int, entity_name: str) -> ModelT:
    """Fetch by id or raise a uniform 404 — replaces the
    `obj = await repo.get(id); if obj is None: raise HTTPException(404, ...)`
    pattern that was duplicated in every PATCH/DELETE endpoint."""
    obj: Optional[ModelT] = await repo.get(id_)
    if obj is None:
        raise NotFoundError(f"{entity_name} not found")
    return obj


async def resolve_profile_id(
    db: AsyncSession, user: "User", requested_id: Optional[int]
) -> Optional[int]:
    """Shared by /api/leads and /api/analytics/overview (both work "in the
    context of a SearchProfile"): None returned = the caller has no
    SearchProfile at all yet (graceful empty state, not an error). An
    explicitly requested id that doesn't belong to this user raises
    NotFoundError — same 404-not-403 pattern used everywhere else in the
    API (see app/api/search_profiles.py)."""
    repo = SearchProfileRepository(db)
    if requested_id is not None:
        profile = await repo.get(requested_id)
        if profile is None or profile.user_id != user.id:
            raise NotFoundError("Search profile not found")
        return profile.id
    return await repo.get_first_id_for_user(user.id)
