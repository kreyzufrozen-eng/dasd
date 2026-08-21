"""LeadNotifier: sends the formatted lead card + inline actions to a
Telegram chat. Used by the pipeline worker (Stage 7) right after a Lead
is persisted — kept separate from LeadPipelineService so that service has
no aiogram dependency and stays trivially testable.

chat_id is a per-call argument, not fixed at construction: since Этап 12
(per-user Telegram login), each SearchProfile's owning User may have
their own linked telegram_id — see app/workers/pipeline_worker.py's
_resolve_notification_chat_id for the "user's own chat, falling back to
the shared NOTIFICATION_CHAT_ID" routing logic.
"""
from typing import Optional, Union

from aiogram import Bot

from app.bot.formatting import format_lead_notification
from app.bot.keyboards import build_lead_keyboard
from app.core.logging import get_logger
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source

logger = get_logger(__name__)


class LeadNotifier:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def notify_if_qualifying(
        self,
        lead: Lead,
        raw_item: RawItem,
        source: Optional[Source],
        threshold: int,
        chat_id: Union[str, int],
        intent_threshold: Optional[int] = None,
    ) -> bool:
        qualifies_by_score = lead.lead_score >= threshold
        qualifies_by_intent = intent_threshold is not None and lead.intent_score >= intent_threshold
        if not (qualifies_by_score or qualifies_by_intent):
            return False

        text = format_lead_notification(lead, raw_item, source)
        keyboard = build_lead_keyboard(lead.id, raw_item)

        try:
            await self.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
            return True
        except Exception:  # noqa: BLE001 - a failed notification must not crash the worker
            logger.exception("Failed to send Telegram notification for lead id=%s", lead.id)
            return False
