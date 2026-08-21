"""Inline keyboards for lead notifications."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.raw_item import RawItem


class LeadAction(CallbackData, prefix="lead"):
    action: str  # "good" | "not_interesting" | "client" | "archive"
    lead_id: int


def build_lead_keyboard(lead_id: int, raw_item: RawItem) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    if raw_item.url:
        builder.button(text="🔗 Открыть источник", url=raw_item.url)

    builder.button(text="👍 Хороший", callback_data=LeadAction(action="good", lead_id=lead_id))
    builder.button(
        text="👎 Неинтересно", callback_data=LeadAction(action="not_interesting", lead_id=lead_id)
    )
    builder.button(text="💰 Клиент", callback_data=LeadAction(action="client", lead_id=lead_id))
    builder.button(text="🗂 Архив", callback_data=LeadAction(action="archive", lead_id=lead_id))

    builder.adjust(1, 2, 2)
    return builder.as_markup()
