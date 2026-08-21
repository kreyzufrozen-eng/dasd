"""One-time interactive Telegram login — creates the session file that
`pipeline_worker.py` needs to connect non-interactively afterward.

Telethon's `.start()` (used only here, deliberately not in the recurring
worker loop) will prompt for phone number / login code on stdin. Run this
manually whenever TELEGRAM_SESSION has no existing session file yet, e.g.:

    docker compose run --rm worker python -m app.workers.telegram_login

Make sure TELEGRAM_SESSION points inside a path that's persisted via a
volume (see docker-compose.yml's `worker` service) — otherwise you'll have
to log in again every time the container is recreated.
"""
import asyncio

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.sources.telegram_client import create_telegram_client

configure_logging()
logger = get_logger(__name__)


async def main() -> None:
    settings = get_settings()
    client = create_telegram_client(settings)
    async with client:
        me = await client.get_me()
        identity = getattr(me, "username", None) or getattr(me, "id", "unknown")
        logger.info("Telegram login successful as: %s", identity)
        logger.info("Session saved. You can now start the regular worker service.")


if __name__ == "__main__":
    asyncio.run(main())
