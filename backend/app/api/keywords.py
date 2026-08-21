"""REST API: /api/keywords"""
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_404
from app.core.exceptions import ConflictError
from app.db.session import get_db_session
from app.models.keyword import Keyword
from app.repositories.keyword_repository import KeywordRepository
from app.schemas.keyword_schemas import KeywordCreate, KeywordRead, KeywordUpdate

router = APIRouter(prefix="/api/keywords", tags=["keywords"])


@router.get("", response_model=list[KeywordRead])
async def list_keywords(
    category: Optional[str] = None, db: AsyncSession = Depends(get_db_session)
) -> list[Keyword]:
    keyword_repo = KeywordRepository(db)
    return await keyword_repo.list_all(category=category)


@router.post("", response_model=KeywordRead, status_code=201)
async def create_keyword(
    payload: KeywordCreate, db: AsyncSession = Depends(get_db_session)
) -> Keyword:
    # payload.category is already validated against KeywordCategory by
    # KeywordCreate's field_validator.
    keyword_repo = KeywordRepository(db)
    existing = await keyword_repo.get_by_keyword_and_category(payload.keyword, payload.category)
    if existing is not None:
        raise ConflictError("Keyword already exists in this category")

    keyword = await keyword_repo.create(**payload.model_dump())
    await db.commit()
    return keyword


@router.patch("/{keyword_id}", response_model=KeywordRead)
async def update_keyword(
    keyword_id: int, payload: KeywordUpdate, db: AsyncSession = Depends(get_db_session)
) -> Keyword:
    keyword_repo = KeywordRepository(db)
    keyword: Keyword = await get_or_404(keyword_repo, keyword_id, "Keyword")

    update_data = payload.model_dump(exclude_unset=True)
    updated = await keyword_repo.update(keyword, **update_data)
    await db.commit()
    return updated


@router.delete("/{keyword_id}", status_code=204)
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db_session)) -> None:
    keyword_repo = KeywordRepository(db)
    keyword: Keyword = await get_or_404(keyword_repo, keyword_id, "Keyword")

    await keyword_repo.delete(keyword)
    await db.commit()
