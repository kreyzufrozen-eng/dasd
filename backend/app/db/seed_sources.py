"""Idempotent Telegram source seeding from the curated catalog.

Run with: `python -m app.db.seed_sources` (inside the backend container/venv).
Safe to run multiple times: existing (type, external_identifier) rows are
skipped rather than duplicated (Source has no DB-level unique constraint on
that pair, so this check is the only thing preventing dupes on a re-run).

Each row is created with is_active=True and added_by_user_id=None (system
catalog, not tied to any one user) — matching how the pre-migration
production catalog was represented (see Source.category's docstring).
"""
import asyncio

from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.models.enums import SourceType
from app.repositories.source_repository import SourceRepository
from app.services.telegram_source_seed_data import TELEGRAM_SEED_SOURCES

configure_logging()
logger = get_logger(__name__)


async def seed_telegram_sources() -> None:
    async with AsyncSessionLocal() as session:
        repo = SourceRepository(session)
        created = 0
        skipped = 0
        for username in TELEGRAM_SEED_SOURCES:
            existing = await repo.get_by_type_and_identifier(SourceType.TELEGRAM.value, username)
            if existing:
                skipped += 1
                continue
            await repo.create(
                name=username,
                type=SourceType.TELEGRAM.value,
                external_identifier=username,
                is_active=True,
            )
            created += 1
        await session.commit()
        logger.info(
            "Telegram source seeding done: %s created, %s already present", created, skipped
        )


async def main() -> None:
    await seed_telegram_sources()


if __name__ == "__main__":
    asyncio.run(main())
