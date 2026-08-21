"""aiogram bot entrypoint — the `bot` service in docker-compose."""
import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession

from app.bot.handlers import router
from app.bot.public_handlers import public_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    if not settings.BOT_TOKEN:
        logger.warning(
            "BOT_TOKEN is not set — notification bot is idle until it's configured. "
            "Set BOT_TOKEN in .env and restart this service to enable it."
        )
        # Idle forever instead of exiting: this is an expected "not
        # configured yet" state, not a crash. Returning here would exit
        # the container, and docker-compose's `restart: unless-stopped`
        # would then spin it in an endless restart loop, spamming logs
        # every few seconds for no reason.
        await asyncio.Event().wait()
        return

    session = AiohttpSession(proxy=settings.TELEGRAM_PROXY_URL) if settings.TELEGRAM_PROXY_URL else None
    bot = Bot(token=settings.BOT_TOKEN, session=session)
    dispatcher = Dispatcher()
    # public_router first: its CommandStart(deep_link=True) handler must
    # see a deep-link /start (from *any* sender, including the owner
    # testing their own "Войти через Telegram" flow) before router's bare
    # CommandStart() — which is IsOwner-gated but matches /start
    # regardless of payload — would otherwise intercept it for the owner.
    dispatcher.include_router(public_router)
    dispatcher.include_router(router)

    logger.info("ReadHunter bot starting polling")
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
