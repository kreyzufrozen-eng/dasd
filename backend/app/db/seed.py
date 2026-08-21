"""Idempotent DB seeding — currently just the keyword pre-filter list.

Run with: `python -m app.db.seed` (inside the backend container/venv).
Safe to run multiple times: existing (keyword, category) pairs are skipped.
"""
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.repositories.keyword_repository import KeywordRepository
from app.services.keyword_seed_data import SEED_KEYWORDS

configure_logging()
logger = get_logger(__name__)


async def seed_keywords() -> None:
    async with AsyncSessionLocal() as session:
        repo = KeywordRepository(session)
        created = 0
        skipped = 0
        for keyword, category, weight in SEED_KEYWORDS:
            existing = await repo.get_by_keyword_and_category(keyword, category.value)
            if existing:
                skipped += 1
                continue
            await repo.create(keyword=keyword, category=category.value, weight=weight)
            created += 1
        await session.commit()
        logger.info("Keyword seeding done: %s created, %s already present", created, skipped)


async def main() -> None:
    await seed_keywords()


if __name__ == "__main__":
    asyncio.run(main())
