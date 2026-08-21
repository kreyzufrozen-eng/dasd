"""REST API: /api/search-profiles/{profile_id}/keywords — per-profile
keyword list. Unlike sources, these rows belong entirely to the profile
(see app/models/search_profile_keyword.py) — no separate global-vs-linked
distinction to manage here."""
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.search_profile_keyword import SearchProfileKeyword
from app.models.user import User
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.schemas.search_profile_keyword_schemas import (
    SearchProfileKeywordCreate,
    SearchProfileKeywordRead,
    SearchProfileKeywordUpdate,
)

router = APIRouter(tags=["search-profile-keywords"])


async def _get_owned_profile_or_404(db: AsyncSession, profile_id: int, user_id: int):
    profile = await SearchProfileRepository(db).get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise NotFoundError("Search profile not found")
    return profile


@router.get(
    "/api/search-profiles/{profile_id}/keywords", response_model=List[SearchProfileKeywordRead]
)
async def list_profile_keywords(
    profile_id: int,
    category: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[SearchProfileKeyword]:
    await _get_owned_profile_or_404(db, profile_id, user.id)
    return list(
        await SearchProfileKeywordRepository(db).list_for_profile(profile_id, category=category)
    )


@router.post(
    "/api/search-profiles/{profile_id}/keywords",
    response_model=SearchProfileKeywordRead,
    status_code=201,
)
async def create_profile_keyword(
    profile_id: int,
    payload: SearchProfileKeywordCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileKeyword:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    repo = SearchProfileKeywordRepository(db)
    keyword = await repo.create(search_profile_id=profile_id, **payload.model_dump())
    await db.commit()
    return keyword


@router.patch(
    "/api/search-profiles/{profile_id}/keywords/{keyword_id}",
    response_model=SearchProfileKeywordRead,
)
async def update_profile_keyword(
    profile_id: int,
    keyword_id: int,
    payload: SearchProfileKeywordUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileKeyword:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    repo = SearchProfileKeywordRepository(db)
    keyword = await repo.get(keyword_id)
    if keyword is None or keyword.search_profile_id != profile_id:
        raise NotFoundError("Keyword not found")

    update_data = payload.model_dump(exclude_unset=True)
    updated = await repo.update(keyword, **update_data)
    await db.commit()
    return updated


@router.delete("/api/search-profiles/{profile_id}/keywords/{keyword_id}", status_code=204)
async def delete_profile_keyword(
    profile_id: int,
    keyword_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    repo = SearchProfileKeywordRepository(db)
    keyword = await repo.get(keyword_id)
    if keyword is None or keyword.search_profile_id != profile_id:
        raise NotFoundError("Keyword not found")

    await repo.delete(keyword)
    await db.commit()
