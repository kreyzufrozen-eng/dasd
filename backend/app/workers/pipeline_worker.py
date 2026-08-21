"""Worker entrypoint: runs the full pipeline on a fixed interval.

SOURCE -> COLLECT RAW ITEM -> DEDUPLICATION   (TelegramCollectorService)
       -> KEYWORD FILTER -> AI ANALYSIS -> LEAD SCORING -> DATABASE
                                                       (LeadPipelineService)

Each cycle:
1. If Telegram is configured, poll every active + allow-listed Telegram
   source for new messages and persist them as RawItems.
2. Poll every active WEBSITE source (e.g. Kwork projects) the same way.
3. For every active SearchProfile, run that profile's still-pending
   RawItems through the analysis pipeline using that profile's own
   keywords/AI context (Этап 3 — see app/ai/prompts.py). The same
   RawItem can produce a Lead for one profile and nothing for another.

Telegram notification (Stage 8) is intentionally NOT triggered from here —
see app/bot for that; this module's job ends at "Lead saved to DB".
"""
import asyncio
import signal
from typing import Optional

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession

from app.ai.factory import get_ai_provider
from app.bot.notifier import LeadNotifier
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import AsyncSessionLocal
from app.models.enums import SourceType
from app.models.source import Source
from app.models.user import User
from app.repositories.raw_item_repository import RawItemRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.repositories.source_repository import SourceRepository
from app.services.lead_pipeline import LeadPipelineService
from app.services.profile_keyword_seeder import ensure_keywords_seeded
from app.services.telegram_collector import TelegramCollectorService
from app.sources.base import BaseSourceAdapter
from app.sources.flru_adapter import FlRuProjectsAdapter
from app.sources.kwork_adapter import KworkProjectsAdapter
from app.sources.telegram_adapter import TelegramSourceAdapter
from app.sources.telegram_client import create_telegram_client, is_source_allowed
from app.workers.scheduler import IntervalScheduler

configure_logging()
logger = get_logger(__name__)

# How many pending RawItems to run through Filter -> AI -> Score per cycle.
# Raised from the original 100 once the source list grew large enough that
# a 100/cycle pace couldn't keep up with collection volume (backlog kept
# growing faster than it drained). Most items exit at the free, local
# keyword filter without ever reaching the AI provider, so this is cheaper
# than the raw number suggests — only keyword-matching items cost an AI call.
PIPELINE_BATCH_SIZE = 1000

# Leads go stale fast — never analyze a RawItem older than this, regardless
# of when it was actually collected (matters for the historical backlog
# collected before source adapters enforced this at fetch time too).
MAX_LEAD_AGE_DAYS = 5


async def run_telegram_collection() -> None:
    settings = get_settings()

    if not settings.TELEGRAM_API_ID or not settings.TELEGRAM_API_HASH:
        logger.info("Telegram credentials not configured, skipping collection this cycle")
        return

    async with AsyncSessionLocal() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_active(type_=SourceType.TELEGRAM.value)
        allowed_sources = [
            s for s in sources if is_source_allowed(s.external_identifier or "", settings)
        ]

        if not allowed_sources:
            logger.info("No active + allow-listed Telegram sources configured, skipping")
            return

        try:
            client = create_telegram_client(settings)
        except ValueError as exc:
            logger.error("Cannot build Telegram client: %s", exc)
            return

        try:
            await client.connect()
            if not await client.is_user_authorized():
                logger.error(
                    "Telegram client is not authorized. Run "
                    "`python -m app.workers.telegram_login` once interactively to "
                    "create a session file, then restart the worker."
                )
                return

            collector = TelegramCollectorService(session)
            for source in allowed_sources:
                adapter = TelegramSourceAdapter(client, source)
                try:
                    count = await collector.collect_from_source(source, adapter)
                    logger.info("Source id=%s: %d new item(s)", source.id, count)
                    # Commit per source rather than once for the whole
                    # 300+-source list: with one commit at the end, nothing
                    # is visible in the dashboard/API until the entire
                    # cycle finishes, which can take many minutes — results
                    # should show up as they're found, not in one big burst.
                    await session.commit()
                except Exception:  # noqa: BLE001 - one bad source must not stop the rest
                    logger.exception("Failed collecting from source id=%s", source.id)
                    await session.rollback()
        except Exception:
            logger.exception("Telegram collection cycle failed")
            await session.rollback()
        finally:
            await client.disconnect()


# Registry of website sources this worker knows how to poll, keyed by
# Source.external_identifier. Add one entry here per new site adapter —
# the collection loop below stays generic.
def _build_website_adapter(source: Source) -> Optional[BaseSourceAdapter]:
    if source.external_identifier == "kwork_projects":
        return KworkProjectsAdapter(source)
    if source.external_identifier == "flru_projects":
        return FlRuProjectsAdapter(source)
    logger.warning(
        "No website adapter registered for source id=%s (external_identifier=%s)",
        source.id,
        source.external_identifier,
    )
    return None


async def run_website_collection() -> None:
    async with AsyncSessionLocal() as session:
        source_repo = SourceRepository(session)
        sources = await source_repo.list_active(type_=SourceType.WEBSITE.value)

        if not sources:
            return

        collector = TelegramCollectorService(session)  # source-type-agnostic despite the name
        for source in sources:
            adapter = _build_website_adapter(source)
            if adapter is None:
                continue
            try:
                count = await collector.collect_from_source(source, adapter)
                logger.info("Source id=%s: %d new item(s)", source.id, count)
                await session.commit()  # per source — see comment in run_telegram_collection
            except Exception:  # noqa: BLE001 - one bad source must not stop the rest
                logger.exception("Failed collecting from source id=%s", source.id)
                await session.rollback()


async def _resolve_notification_chat_id(session, profile, settings) -> Optional[str]:
    """The profile owner's own linked Telegram chat if they have one
    (Этап 12 — see app/services/telegram_login_service.py); otherwise the
    single shared NOTIFICATION_CHAT_ID, same as every profile used before
    per-user linking existed. Not a new privacy gap: this is the exact
    pre-existing behavior for any user who simply hasn't linked Telegram
    yet, scoped down to fewer profiles as more users link their own chat —
    see SECURITY_REVIEW.md."""
    user = await session.get(User, profile.user_id)
    if user is not None and user.telegram_id is not None:
        return str(user.telegram_id)
    return settings.NOTIFICATION_CHAT_ID


async def _run_pipeline_for_profile(
    session,
    pipeline: LeadPipelineService,
    profile,
    raw_repo: RawItemRepository,
    source_repo: SourceRepository,
    notifier: Optional[LeadNotifier],
    settings,
) -> None:
    """Этап 3: the per-profile body of what used to be run once for the
    single "primary" profile — now called once per active SearchProfile
    (see run_lead_pipeline). Keeps its own keyword filter and its own
    pending-items query, since both are profile-scoped."""
    await ensure_keywords_seeded(session, profile.id)

    pending_items = await raw_repo.list_without_lead(
        search_profile_id=profile.id,
        limit=PIPELINE_BATCH_SIZE,
        max_age_days=MAX_LEAD_AGE_DAYS,
    )
    if not pending_items:
        return

    keyword_filter = await pipeline.build_keyword_filter(profile.id)
    logger.info(
        "Processing %d pending raw item(s) for profile id=%s (%s)",
        len(pending_items),
        profile.id,
        profile.name,
    )

    for item in pending_items:
        try:
            result = await pipeline.process_raw_item(
                item, search_profile=profile, keyword_filter=keyword_filter
            )
            # Commit per item rather than once for the whole batch of up
            # to PIPELINE_BATCH_SIZE: a single end-of-batch commit means
            # nothing shows up in the dashboard until every item
            # (including slow AI calls) has been processed — leads should
            # appear as they're found.
            await session.commit()
        except Exception:  # noqa: BLE001 - one bad item must not stop the rest
            logger.exception(
                "Pipeline processing failed for raw_item id=%s profile id=%s",
                item.id,
                profile.id,
            )
            await session.rollback()
            continue

        # Notify only after the commit above, so a notification is never
        # sent for a Lead that doesn't actually exist in the DB. Qualifies
        # via lead_score (explicit request) OR intent_score (hidden
        # demand) — notify_if_qualifying checks both thresholds. Routed to
        # this profile's owner's own linked Telegram chat if they have
        # one, else the shared NOTIFICATION_CHAT_ID (see
        # _resolve_notification_chat_id above).
        if (
            notifier is not None
            and result.is_new
            and result.lead is not None
            and (
                result.lead.lead_score >= settings.NOTIFICATION_THRESHOLD
                or result.lead.intent_score >= settings.INTENT_NOTIFICATION_THRESHOLD
            )
        ):
            chat_id = await _resolve_notification_chat_id(session, profile, settings)
            if chat_id is not None:
                source = await source_repo.get(item.source_id)
                await notifier.notify_if_qualifying(
                    result.lead,
                    item,
                    source,
                    settings.NOTIFICATION_THRESHOLD,
                    chat_id=chat_id,
                    intent_threshold=settings.INTENT_NOTIFICATION_THRESHOLD,
                )


async def run_lead_pipeline() -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        try:
            ai_provider = get_ai_provider(settings)
        except ValueError as exc:
            logger.error("Cannot build AI provider: %s", exc)
            return

        pipeline = LeadPipelineService(session, ai_provider, settings)
        raw_repo = RawItemRepository(session)
        source_repo = SourceRepository(session)
        search_profile_repo = SearchProfileRepository(session)

        active_profiles = await search_profile_repo.list_active()
        if not active_profiles:
            logger.error(
                "No active SearchProfile exists — nothing to attach leads to. "
                "Run migration 0004 or create one via POST /api/search-profiles."
            )
            return

        bot: Optional[Bot] = None
        notifier: Optional[LeadNotifier] = None
        # Only BOT_TOKEN is required now — the per-profile chat_id comes
        # from _resolve_notification_chat_id (the owner's own linked
        # Telegram, falling back to NOTIFICATION_CHAT_ID if unset/unlinked).
        if settings.BOT_TOKEN:
            proxy_session = (
                AiohttpSession(proxy=settings.TELEGRAM_PROXY_URL)
                if settings.TELEGRAM_PROXY_URL
                else None
            )
            bot = Bot(token=settings.BOT_TOKEN, session=proxy_session)
            notifier = LeadNotifier(bot)
        else:
            logger.info(
                "BOT_TOKEN not configured — qualifying leads this cycle will be "
                "saved but no Telegram notification will be sent"
            )

        try:
            for profile in active_profiles:
                await _run_pipeline_for_profile(
                    session, pipeline, profile, raw_repo, source_repo, notifier, settings
                )
        finally:
            if bot is not None:
                await bot.session.close()


async def run_cycle() -> None:
    await run_telegram_collection()
    await run_website_collection()
    await run_lead_pipeline()


async def main() -> None:
    settings = get_settings()
    scheduler = IntervalScheduler(interval_seconds=settings.TELEGRAM_POLL_INTERVAL_SECONDS)

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, scheduler.stop)
        except NotImplementedError:
            pass  # signal handlers unsupported on this platform (e.g. some Windows setups)

    logger.info(
        "Pipeline worker starting, interval=%ss", settings.TELEGRAM_POLL_INTERVAL_SECONDS
    )
    await scheduler.run_forever(run_cycle)
    logger.info("Pipeline worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
