"""REST API: /api/sources"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_or_404
from app.db.session import get_db_session
from app.models.source import Source
from app.repositories.lead_repository import LeadRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.source_schemas import SourceCreate, SourceRead, SourceUpdate, SourceWithLeadCount

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceWithLeadCount])
async def list_sources(db: AsyncSession = Depends(get_db_session)) -> list[SourceWithLeadCount]:
    source_repo = SourceRepository(db)
    lead_repo = LeadRepository(db)

    sources = await source_repo.list(limit=1000)
    results = []
    for source in sources:
        lead_count = await lead_repo.count_for_source(source.id)
        results.append(
            SourceWithLeadCount(**SourceRead.model_validate(source).model_dump(), lead_count=lead_count)
        )
    return results


@router.post("", response_model=SourceRead, status_code=201)
async def create_source(payload: SourceCreate, db: AsyncSession = Depends(get_db_session)) -> Source:
    # payload.type is already validated against SourceType by
    # SourceCreate's field_validator.
    source_repo = SourceRepository(db)
    source = await source_repo.create(**payload.model_dump())
    await db.commit()
    return source


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: int, payload: SourceUpdate, db: AsyncSession = Depends(get_db_session)
) -> Source:
    source_repo = SourceRepository(db)
    source: Source = await get_or_404(source_repo, source_id, "Source")

    update_data = payload.model_dump(exclude_unset=True)
    updated = await source_repo.update(source, **update_data)
    await db.commit()
    return updated


@router.delete("/{source_id}", status_code=204)
async def delete_source(source_id: int, db: AsyncSession = Depends(get_db_session)) -> None:
    source_repo = SourceRepository(db)
    source: Source = await get_or_404(source_repo, source_id, "Source")

    await source_repo.delete(source)
    await db.commit()
