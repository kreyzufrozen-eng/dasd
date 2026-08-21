"""REST API: /api/search-profiles/{profile_id}/sources — per-profile
source links, plus /api/sources/catalog for browsing what's available to
link. Ownership of the SearchProfile is checked on every route; Source
rows themselves are shared/global (see app/models/source.py)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.security import get_current_user
from app.db.session import get_db_session
from app.models.search_profile_source import SearchProfileSource
from app.models.user import User
from app.repositories.search_profile_repository import SearchProfileRepository
from app.repositories.search_profile_source_repository import SearchProfileSourceRepository
from app.repositories.source_repository import SourceRepository
from app.schemas.search_profile_source_schemas import (
    SearchProfileSourceAttach,
    SearchProfileSourceBulkAttach,
    SearchProfileSourceBulkAttachResult,
    SearchProfileSourceCreateCustom,
    SearchProfileSourceRead,
    SearchProfileSourceUpdate,
)
from app.schemas.source_schemas import SourceCatalogEntry

router = APIRouter(tags=["search-profile-sources"])


async def _get_owned_profile_or_404(db: AsyncSession, profile_id: int, user_id: int):
    profile = await SearchProfileRepository(db).get(profile_id)
    if profile is None or profile.user_id != user_id:
        raise NotFoundError("Search profile not found")
    return profile


@router.get(
    "/api/search-profiles/{profile_id}/sources", response_model=List[SearchProfileSourceRead]
)
async def list_profile_sources(
    profile_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[SearchProfileSource]:
    await _get_owned_profile_or_404(db, profile_id, user.id)
    return list(await SearchProfileSourceRepository(db).list_for_profile(profile_id))


@router.post(
    "/api/search-profiles/{profile_id}/sources",
    response_model=SearchProfileSourceRead,
    status_code=201,
)
async def attach_profile_source(
    profile_id: int,
    payload: SearchProfileSourceAttach,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileSource:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    source_repo = SourceRepository(db)
    source = await source_repo.get(payload.source_id)
    if source is None:
        raise NotFoundError("Source not found")

    link_repo = SearchProfileSourceRepository(db)
    existing = await link_repo.get_link(profile_id, payload.source_id)
    if existing is not None:
        updated = await link_repo.update(existing, enabled=payload.enabled)
        await db.commit()
        return await link_repo.get_with_source(updated.id)  # type: ignore[return-value]

    link = await link_repo.create(
        search_profile_id=profile_id, source_id=payload.source_id, enabled=payload.enabled
    )
    await db.commit()
    return await link_repo.get_with_source(link.id)  # type: ignore[return-value]


@router.post(
    "/api/search-profiles/{profile_id}/sources/bulk",
    response_model=SearchProfileSourceBulkAttachResult,
    status_code=201,
)
async def bulk_attach_profile_sources(
    profile_id: int,
    payload: SearchProfileSourceBulkAttach,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileSourceBulkAttachResult:
    """One round trip for attaching many sources at once — e.g. onboarding's
    "наша база источников" bulk-select, which can be a few hundred ids.
    See SearchProfileSourceRepository.bulk_attach for why this exists
    instead of N calls to the single-attach endpoint above."""
    await _get_owned_profile_or_404(db, profile_id, user.id)

    link_repo = SearchProfileSourceRepository(db)
    attached = await link_repo.bulk_attach(profile_id, payload.source_ids)
    await db.commit()
    return SearchProfileSourceBulkAttachResult(attached=attached)


@router.post(
    "/api/search-profiles/{profile_id}/sources/custom",
    response_model=SearchProfileSourceRead,
    status_code=201,
)
async def add_custom_profile_source(
    profile_id: int,
    payload: SearchProfileSourceCreateCustom,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileSource:
    """Adds the user's own Telegram chat/channel link — dedups against an
    existing Source with the same (type, external_identifier) rather than
    ever creating a duplicate row (would break RawItem dedup and double
    the parsing work for that channel)."""
    await _get_owned_profile_or_404(db, profile_id, user.id)

    source_repo = SourceRepository(db)
    source = None
    if payload.external_identifier:
        source = await source_repo.get_by_type_and_identifier(
            payload.type, payload.external_identifier
        )
    if source is None:
        source = await source_repo.create(
            name=payload.name,
            type=payload.type,
            url=payload.url,
            external_identifier=payload.external_identifier,
            added_by_user_id=user.id,
        )

    link_repo = SearchProfileSourceRepository(db)
    existing = await link_repo.get_link(profile_id, source.id)
    if existing is not None:
        await db.commit()
        return await link_repo.get_with_source(existing.id)  # type: ignore[return-value]

    link = await link_repo.create(search_profile_id=profile_id, source_id=source.id, enabled=True)
    await db.commit()
    return await link_repo.get_with_source(link.id)  # type: ignore[return-value]


@router.patch(
    "/api/search-profiles/{profile_id}/sources/{source_id}",
    response_model=SearchProfileSourceRead,
)
async def update_profile_source(
    profile_id: int,
    source_id: int,
    payload: SearchProfileSourceUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> SearchProfileSource:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    link_repo = SearchProfileSourceRepository(db)
    link = await link_repo.get_link(profile_id, source_id)
    if link is None:
        raise NotFoundError("Source not linked to this search profile")

    updated = await link_repo.update(link, enabled=payload.enabled)
    await db.commit()
    return await link_repo.get_with_source(updated.id)  # type: ignore[return-value]


@router.delete("/api/search-profiles/{profile_id}/sources/{source_id}", status_code=204)
async def detach_profile_source(
    profile_id: int,
    source_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    await _get_owned_profile_or_404(db, profile_id, user.id)

    link_repo = SearchProfileSourceRepository(db)
    link = await link_repo.get_link(profile_id, source_id)
    if link is None:
        raise NotFoundError("Source not linked to this search profile")

    await link_repo.delete(link)
    await db.commit()


@router.get("/api/sources/catalog", response_model=List[SourceCatalogEntry])
async def browse_source_catalog(
    search_profile_id: Optional[int] = Query(
        default=None, description="Annotate each entry with this profile's link state"
    ),
    category: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[SourceCatalogEntry]:
    if search_profile_id is not None:
        await _get_owned_profile_or_404(db, search_profile_id, user.id)

    source_repo = SourceRepository(db)
    sources = await source_repo.list(limit=2000)
    if category:
        sources = [s for s in sources if s.category == category]

    linked_by_source_id: dict[int, SearchProfileSource] = {}
    if search_profile_id is not None:
        link_repo = SearchProfileSourceRepository(db)
        links = await link_repo.list_for_profile(search_profile_id)
        linked_by_source_id = {link.source_id: link for link in links}

    results = []
    for source in sources:
        link = linked_by_source_id.get(source.id)
        results.append(
            SourceCatalogEntry(
                **{
                    k: getattr(source, k)
                    for k in (
                        "id",
                        "name",
                        "type",
                        "url",
                        "external_identifier",
                        "is_active",
                        "category",
                        "last_checked_at",
                        "created_at",
                        "updated_at",
                    )
                },
                already_added=link is not None,
                enabled_for_profile=bool(link and link.enabled),
            )
        )
    return results
