"""Public router — NOT gated by IsOwner (see app/bot/handlers.py's
docstring on why that filter exists for the rest of the bot). This
handles everything any stranger who finds the bot is allowed to trigger:
/start (both a bare "how do I use this" tap and a "Войти через Telegram"
deep-link confirmation), the subscribe-to-channel gate on that bare tap,
and reading the privacy policy. Must be registered on the Dispatcher
*before* the IsOwner-gated router — a plain CommandStart() here matches
every /start regardless of sender, so it's what actually answers a
stranger's bare /start (handlers.py's own CommandStart() would otherwise
silently drop it via IsOwner, since a router only falls through to the
next one when nothing in the current router matches at all).
"""
from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import AsyncSessionLocal
from app.services.telegram_login_service import confirm

logger = get_logger(__name__)

public_router = Router(name="readhunter_public")

# Anyone tapping a bare /start must be subscribed to this channel before
# they can use the bot — see cmd_start below. Must be a public channel
# with the bot added as an admin: get_chat_member on a channel only works
# for chats the bot itself is a member of, and channels only ever have
# admin bot members (there's no plain "member" bot on a channel).
REQUIRED_CHANNEL = "@readhunter"
_SUBSCRIBED_STATUSES = {"creator", "administrator", "member"}


async def _is_subscribed(bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
    except TelegramAPIError as exc:
        # Fails open: if the bot isn't (yet) an admin of the channel, or
        # Telegram is briefly unreachable, that's an infra problem — it
        # shouldn't lock every single user out of the whole bot.
        logger.warning(
            "Could not check %s membership for user_id=%s: %s", REQUIRED_CHANNEL, user_id, exc
        )
        return True
    return member.status in _SUBSCRIBED_STATUSES


def _welcome_text(site_url: str) -> str:
    return (
        "👋 Привет! Я бот ReadHunter — ищу для вас клиентов и лидов "
        "по вашим ключевым словам и источникам.\n\n"
        f"Чтобы начать пользоваться, перейдите на сайт:\n{site_url}\n\n"
        "Там можно войти прямо через Telegram."
    )


def _subscribe_prompt() -> str:
    return (
        f"📢 Чтобы начать пользоваться ботом ReadHunter, сначала подпишитесь "
        f"на канал {REQUIRED_CHANNEL} — там анонсы и обновления сервиса.\n\n"
        "После подписки нажмите кнопку ниже."
    )


def _subscribe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📢 Подписаться на {REQUIRED_CHANNEL}",
                    url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}",
                )
            ],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
        ]
    )


@public_router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject) -> None:
    payload = command.args
    user = message.from_user

    if not payload:
        # Bare /start — someone found the bot directly rather than via a
        # site-issued deep link. Gate on channel subscription first; once
        # subscribed (or if we can't check — see _is_subscribed) point
        # them at the site instead of answering with nothing (the old
        # behavior for anyone but the bot owner).
        if user is not None and not await _is_subscribed(message.bot, user.id):
            await message.answer(_subscribe_prompt(), reply_markup=_subscribe_keyboard())
            return
        settings = get_settings()
        await message.answer(_welcome_text(settings.PUBLIC_SITE_URL))
        return

    if user is None:
        await message.answer("Ссылка недействительна. Начните вход заново на сайте.")
        return

    async with AsyncSessionLocal() as session:
        ok = await confirm(
            session,
            payload,
            telegram_id=user.id,
            telegram_username=user.username,
            telegram_first_name=user.first_name,
        )

    if ok:
        await message.answer(
            "✅ Вход подтверждён! Вернитесь на сайт ReadHunter — вы уже вошли."
        )
    else:
        await message.answer(
            "⏱ Эта ссылка уже использована или её срок истёк. "
            "Вернитесь на сайт и запросите вход через Telegram заново."
        )


@public_router.callback_query(F.data == "check_subscription")
async def cb_check_subscription(callback: CallbackQuery) -> None:
    user = callback.from_user
    if not await _is_subscribed(callback.bot, user.id):
        await callback.answer(
            "Пока не вижу подписку 🙈 Подпишитесь на канал и нажмите кнопку ещё раз.",
            show_alert=True,
        )
        return

    settings = get_settings()
    if callback.message is not None:
        await callback.message.edit_text(_welcome_text(settings.PUBLIC_SITE_URL))
    await callback.answer("Спасибо за подписку! ✅")


@public_router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    settings = get_settings()
    await message.answer(f"📄 Политика обработки персональных данных:\n{settings.PUBLIC_SITE_URL}/privacy")
