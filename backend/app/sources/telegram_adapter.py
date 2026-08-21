"""TelegramSourceAdapter: fetches new messages from one allowed public
Telegram source via Telethon.

Design notes (per project rules):
- Only ever reads from sources the connected account can already access
  publicly — no join-by-invite-link automation, no bypassing privacy
  settings, no scraping outside the official Telegram client API.
- Bookkeeping (`Source.last_external_id`) is the caller's responsibility
  to persist after a successful batch — this adapter is stateless between
  calls so it has no in-memory state that can be lost on restart.
- A single bad message or a rate limit must not crash the whole poll
  cycle for every other source; every failure path here is caught,
  logged, and degrades to "return whatever was fetched so far".
"""
import datetime as dt
from typing import Any, Optional

from telethon import TelegramClient
from telethon.errors import FloodWaitError, RPCError

from app.core.logging import get_logger
from app.models.source import Source
from app.sources.base import BaseSourceAdapter, RawItemDTO

logger = get_logger(__name__)

DEFAULT_FETCH_LIMIT = 200
# Never pull messages older than this, even for a brand-new source with no
# watermark yet, and even for a source whose stored watermark is already
# deep in old history (e.g. a channel that's been slowly crawling forward
# from message #1 for a while) — leads go stale fast, so there's no value
# in ever walking a channel's multi-year history.
#
# This can't be done with iter_messages(offset_date=...): Telegram gives
# offset_id priority over offset_date whenever both are present, and
# min_id always becomes a non-zero offset_id once a source has any
# watermark at all — so offset_date is silently ignored for every source
# except a genuinely brand-new one. Instead we resolve the message id at
# the cutoff date once per source per cycle and use max(watermark,
# cutoff_id) as min_id, which Telegram always honors.
MAX_HISTORY_DAYS = 5


class TelegramSourceAdapter(BaseSourceAdapter):
    def __init__(
        self, client: TelegramClient, source: Source, fetch_limit: int = DEFAULT_FETCH_LIMIT
    ) -> None:
        self.client = client
        self.source = source
        self.fetch_limit = fetch_limit

    async def fetch_new_items(self) -> list[RawItemDTO]:
        identifier = self.source.external_identifier
        if not identifier:
            logger.warning("Source id=%s has no external_identifier, skipping", self.source.id)
            return []

        min_id = int(self.source.last_external_id) if self.source.last_external_id else 0
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MAX_HISTORY_DAYS)
        cutoff_id = await self._resolve_cutoff_id(identifier, cutoff)
        effective_min_id = max(min_id, cutoff_id)
        items: list[RawItemDTO] = []

        try:
            async for message in self.client.iter_messages(
                identifier, min_id=effective_min_id, reverse=True, limit=self.fetch_limit
            ):
                dto = await self._message_to_dto(message, identifier)
                if dto is not None:
                    items.append(dto)
        except FloodWaitError as exc:
            logger.warning(
                "Telegram rate limit hit for source '%s': must wait %s seconds. "
                "Returning %d items collected before the limit.",
                identifier,
                exc.seconds,
                len(items),
            )
        except RPCError as exc:
            logger.exception("Telegram RPC error while fetching source '%s': %s", identifier, exc)
        except Exception as exc:  # noqa: BLE001 - one bad source must not kill the poll cycle
            logger.exception(
                "Unexpected error fetching Telegram source '%s': %s", identifier, exc
            )

        return items

    async def _resolve_cutoff_id(self, identifier: str, cutoff: dt.datetime) -> int:
        """Id of the newest message strictly older than `cutoff` (0 if the
        whole channel is already newer than `cutoff`, or on lookup
        failure) — safe to use directly as a `min_id` floor."""
        try:
            messages = await self.client.get_messages(identifier, limit=1, offset_date=cutoff)
        except Exception as exc:  # noqa: BLE001 - a failed lookup just means no extra floor
            logger.warning(
                "Could not resolve %s-day cutoff id for '%s': %s",
                MAX_HISTORY_DAYS,
                identifier,
                exc,
            )
            return 0
        if not messages:
            return 0
        return getattr(messages[0], "id", 0) or 0

    async def _message_to_dto(self, message: Any, identifier: str) -> Optional[RawItemDTO]:
        text = (getattr(message, "message", None) or "").strip()
        if not text:
            return None

        author_name: Optional[str] = None
        author_username: Optional[str] = None
        try:
            sender = await message.get_sender()
            if sender is not None:
                author_username = getattr(sender, "username", None)
                first = getattr(sender, "first_name", "") or ""
                last = getattr(sender, "last_name", "") or ""
                combined = f"{first} {last}".strip()
                author_name = combined or getattr(sender, "title", None)
        except Exception as exc:  # noqa: BLE001 - sender resolution is best-effort
            logger.warning(
                "Could not resolve sender for message %s in '%s': %s",
                getattr(message, "id", "?"),
                identifier,
                exc,
            )

        return RawItemDTO(
            external_id=str(message.id),
            text=text,
            author_name=author_name,
            author_username=author_username,
            url=f"https://t.me/{identifier}/{message.id}",
            published_at=getattr(message, "date", None),
            metadata={"telegram_channel": identifier},
        )
