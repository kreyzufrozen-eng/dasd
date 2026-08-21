"""aiogram Router: owner-only commands (/leads, /hot, /stats) and inline
button callbacks. Each handler opens its own short-lived DB session —
simplest thing that works for an MVP bot, no DI middleware needed.

/start is NOT handled here — app/bot/public_handlers.py's public_router
(registered before this one on the Dispatcher, see app/bot/run_bot.py)
owns every /start, bare or with a deep-link payload, so it works for any
sender, not just the owner.
"""
from typing import Union

from aiogram import Router
from aiogram.filters import Command, Filter
from aiogram.types import CallbackQuery, Message

from app.bot.formatting import format_lead_summary_line, format_stats_message
from app.bot.keyboards import LeadAction
from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.models.enums import LeadFeedbackType, LeadStatus
from app.repositories.lead_feedback_repository import LeadFeedbackRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.search_profile_repository import SearchProfileRepository
from app.services.lead_stats import LeadStatsService

logger = get_logger(__name__)


class IsOwner(Filter):
    """Restricts every handler on `router` to the bot's owner.

    Previously any Telegram user who found this bot (it's discoverable by
    username) could run /leads, /hot, /stats to read all lead data —
    including author names/usernames and business details — and could
    forge LeadAction callback data to overwrite lead statuses, since
    aiogram's CallbackData encoding is a documented, predictable format
    anyone can construct. Applied once at the router level (below) rather
    than repeated in each handler.
    """

    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        settings = get_settings()
        owner_chat_id = settings.NOTIFICATION_CHAT_ID
        user = event.from_user
        if not owner_chat_id or user is None:
            return False
        return str(user.id) == str(owner_chat_id)


router = Router(name="readhunter")
router.message.filter(IsOwner())
router.callback_query.filter(IsOwner())

# action -> (LeadFeedbackType, LeadStatus, acknowledgement text)
ACTION_MAP = {
    "good": (LeadFeedbackType.GOOD.value, LeadStatus.INTERESTED.value, "Отмечено: хороший лид 👍"),
    "not_interesting": (
        LeadFeedbackType.NOT_INTERESTING.value,
        LeadStatus.REJECTED.value,
        "Отмечено: неинтересно 👎",
    ),
    "client": (LeadFeedbackType.CLIENT.value, LeadStatus.CONVERTED.value, "Отмечено: клиент 💰"),
    "archive": (LeadFeedbackType.ARCHIVED.value, LeadStatus.ARCHIVED.value, "Отправлено в архив 🗂"),
}


@router.message(Command("leads"))
async def cmd_leads(message: Message) -> None:
    async with AsyncSessionLocal() as session:
        profile = await SearchProfileRepository(session).get_primary()
        if profile is None:
            await message.answer("Профиль поиска ещё не настроен.")
            return
        lead_repo = LeadRepository(session)
        leads = await lead_repo.search(search_profile_id=profile.id, limit=10)

    if not leads:
        await message.answer("Лидов пока нет.")
        return

    body = "\n\n".join(format_lead_summary_line(lead) for lead in leads)
    await message.answer(f"📋 Последние лиды:\n\n{body}")


@router.message(Command("hot"))
async def cmd_hot(message: Message) -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        profile = await SearchProfileRepository(session).get_primary()
        if profile is None:
            await message.answer("Профиль поиска ещё не настроен.")
            return
        lead_repo = LeadRepository(session)
        leads = await lead_repo.search(
            search_profile_id=profile.id,
            score_min=settings.NOTIFICATION_THRESHOLD,
            sort="score",
            limit=10,
        )

    if not leads:
        await message.answer("Горячих лидов пока нет.")
        return

    body = "\n\n".join(format_lead_summary_line(lead) for lead in leads)
    await message.answer(f"🔥 Горячие лиды:\n\n{body}")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    settings = get_settings()
    async with AsyncSessionLocal() as session:
        profile = await SearchProfileRepository(session).get_primary()
        if profile is None:
            await message.answer("Профиль поиска ещё не настроен.")
            return
        stats_service = LeadStatsService(
            session,
            notification_threshold=settings.NOTIFICATION_THRESHOLD,
            search_profile_id=profile.id,
        )
        overview = await stats_service.get_overview()

    await message.answer(
        format_stats_message(overview.total, overview.today, overview.hot, overview.converted)
    )


@router.callback_query(LeadAction.filter())
async def handle_lead_action(callback: CallbackQuery, callback_data: LeadAction) -> None:
    mapping = ACTION_MAP.get(callback_data.action)
    if mapping is None:
        logger.warning("Unknown lead action received: %s", callback_data.action)
        await callback.answer("Неизвестное действие", show_alert=True)
        return

    feedback_type, new_status, ack_text = mapping

    async with AsyncSessionLocal() as session:
        lead_repo = LeadRepository(session)
        feedback_repo = LeadFeedbackRepository(session)

        lead = await lead_repo.get(callback_data.lead_id)
        if lead is None:
            await callback.answer("Лид не найден", show_alert=True)
            return

        await feedback_repo.create(lead_id=lead.id, feedback_type=feedback_type)
        await lead_repo.update(lead, status=new_status)
        await session.commit()

    await callback.answer(ack_text)

    if callback.message is not None:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:  # noqa: BLE001 - purely cosmetic, never worth failing the callback over
            logger.debug("Could not clear inline keyboard after action", exc_info=True)
