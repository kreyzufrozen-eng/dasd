"""Ensures a SearchProfile has its own keyword list before the pipeline
(or the keywords UI) needs one.

Two cases this covers:
1. A profile that predates SearchProfileKeyword entirely (every profile
   that existed before Этап 2's migration 0005) — without this, Этап 3's
   per-profile pipeline would see zero keywords for it and stop finding
   leads it used to find, since the old pipeline matched against the
   *entire* global Keyword catalog unscoped. Backfilling from that same
   catalog the first time the profile is touched keeps behavior identical.
2. A profile created via the plain CRUD API without going through
   onboarding's AI keyword generation (Этап 4) — same fallback.

Idempotent and cheap: a single count query short-circuits everything once
a profile has any keyword rows, however they got there.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.keyword_repository import KeywordRepository
from app.repositories.search_profile_keyword_repository import SearchProfileKeywordRepository


async def ensure_keywords_seeded(session: AsyncSession, search_profile_id: int) -> None:
    spk_repo = SearchProfileKeywordRepository(session)
    existing = await spk_repo.list_for_profile(search_profile_id)
    if existing:
        return

    keyword_repo = KeywordRepository(session)
    global_keywords = await keyword_repo.list_active()
    if not global_keywords:
        return

    await spk_repo.bulk_create(
        search_profile_id,
        [
            {
                "keyword_id": kw.id,
                "text": kw.keyword,
                "category": kw.category,
                "weight": kw.weight,
                "enabled": True,
            }
            for kw in global_keywords
        ],
    )
