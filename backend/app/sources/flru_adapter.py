"""FlRuProjectsAdapter: fetches new client project postings from
https://www.fl.ru/projects/ — a public freelance-project marketplace.

Same policy as KworkProjectsAdapter (see app/sources/kwork_adapter.py):
FL.ru has no official public API for project listings, and its RSS feed
is explicitly disallowed for bots (robots.txt: `Disallow: */rss/*` under
`User-agent: *`), so we don't touch it. The plain `/projects/` listing
page itself is NOT disallowed, and is served fully rendered (no JS
required — verified by comparing a plain HTTP fetch against a real
browser render), so this parses that HTML directly. It's markup-based
(FL.ru has no embedded JSON state like Kwork does), so it's more exposed
to breaking on a redesign than the Kwork adapter — that's an accepted
trade-off, not an oversight.
"""
import datetime as dt
import re
from typing import Any, Optional

import httpx
from bs4 import BeautifulSoup

from app.core.logging import get_logger
from app.models.source import Source
from app.sources.base import BaseSourceAdapter, RawItemDTO

logger = get_logger(__name__)

FLRU_BASE_URL = "https://www.fl.ru"
FLRU_PROJECTS_URL = f"{FLRU_BASE_URL}/projects/"
USER_AGENT = "ReadHunterBot/1.0 (+https://www.fl.ru/projects public listing reader)"
DEFAULT_MAX_PAGES = 3
MAX_AGE_DAYS = 5

_MONTHS_GENITIVE = {
    "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
    "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12,
}
_RELATIVE_MINUTES_RE = re.compile(r"(\d+)\s*минут")
_RELATIVE_HOURS_RE = re.compile(r"(\d+)\s*час")
_RELATIVE_DAYS_RE = re.compile(r"(\d+)\s*(?:дня|дней|день)\s*назад")
_ABSOLUTE_DATE_RE = re.compile(r"(\d{1,2})\s+([а-я]+),\s*(\d{1,2}):(\d{2})")


def _parse_posted_at(text: str, now: dt.datetime) -> Optional[dt.datetime]:
    """Best-effort parse of FL.ru's relative/absolute Russian timestamps —
    e.g. "5 минут назад", "1 час 13 минут назад", "14 августа, 15:21"."""
    text = text.strip().lower()
    if not text:
        return None

    if "назад" in text:
        days_match = _RELATIVE_DAYS_RE.search(text)
        if days_match:
            return now - dt.timedelta(days=int(days_match.group(1)))
        hours_match = _RELATIVE_HOURS_RE.search(text)
        minutes_match = _RELATIVE_MINUTES_RE.search(text)
        if hours_match or minutes_match:
            hours = int(hours_match.group(1)) if hours_match else 0
            minutes = int(minutes_match.group(1)) if minutes_match else 0
            return now - dt.timedelta(hours=hours, minutes=minutes)

    abs_match = _ABSOLUTE_DATE_RE.search(text)
    if abs_match:
        day, month_name, hour, minute = abs_match.groups()
        month = _MONTHS_GENITIVE.get(month_name)
        if month is not None:
            try:
                candidate = dt.datetime(
                    now.year, month, int(day), int(hour), int(minute), tzinfo=dt.timezone.utc
                )
            except ValueError:
                return None
            # Listings only ever show recent dates — if the parsed date
            # looks like it's in the future, it must actually be from
            # last year (e.g. viewing "31 декабря" listings in January).
            if candidate > now + dt.timedelta(days=1):
                candidate = candidate.replace(year=now.year - 1)
            return candidate

    return None


class FlRuProjectsAdapter(BaseSourceAdapter):
    def __init__(
        self, source: Source, max_pages: int = DEFAULT_MAX_PAGES, timeout: float = 20.0
    ) -> None:
        self.source = source
        self.max_pages = max_pages
        self.timeout = timeout

    async def fetch_new_items(self) -> list[RawItemDTO]:
        last_seen = self._to_int_or_none(self.source.last_external_id) or 0
        now = dt.datetime.now(dt.timezone.utc)
        cutoff = now - dt.timedelta(days=MAX_AGE_DAYS)
        items: list[RawItemDTO] = []

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT}, timeout=self.timeout
            ) as client:
                for page in range(1, self.max_pages + 1):
                    url = FLRU_PROJECTS_URL if page == 1 else f"{FLRU_BASE_URL}/projects/page-{page}/"
                    response = await client.get(url)
                    response.raise_for_status()
                    cards = self._extract_cards(response.text)
                    if not cards:
                        break

                    stop_paging = False
                    for card in cards:
                        project_id = card.get("id")
                        if project_id is None or project_id <= last_seen:
                            stop_paging = True
                            continue
                        published_at = card.get("published_at")
                        if published_at is not None and published_at < cutoff:
                            stop_paging = True
                            continue
                        dto = self._card_to_dto(card)
                        if dto is not None:
                            items.append(dto)

                    if stop_paging:
                        break
        except httpx.HTTPError as exc:
            logger.warning(
                "FL.ru projects fetch failed: %s. Returning %d item(s) collected so far.",
                exc,
                len(items),
            )
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the poll cycle
            logger.exception("Unexpected error fetching FL.ru projects: %s", exc)

        return items

    def _extract_cards(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        now = dt.datetime.now(dt.timezone.utc)
        cards: list[dict[str, Any]] = []

        # Each project's full card (title, price, description AND the
        # "N minutes ago" timestamp, which lives in a separate trailing
        # <div class="b-post__foot"> sibling) is wrapped by one
        # `<div id="project-item{id}">` — that's the right scope to
        # search within, not the <h2>'s immediate parent.
        for wrapper in soup.select('div[id^="project-item"]'):
            link = wrapper.select_one("a[data-disposable-project-id]")
            if link is None:
                continue
            project_id = self._to_int_or_none(link.get("data-disposable-project-id"))
            if project_id is None:
                continue

            title = link.get_text(strip=True)
            href = link.get("href") or ""

            price_el = wrapper.select_one(".b-post__price")
            desc_el = wrapper.select_one(".b-post__txt")
            time_el = wrapper.select_one(".text-gray-opacity-4.text-7")

            cards.append(
                {
                    "id": project_id,
                    "title": title,
                    "url": href,
                    "price": price_el.get_text(strip=True) if price_el else None,
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                    "published_at": _parse_posted_at(time_el.get_text() if time_el else "", now),
                }
            )

        return cards

    def _card_to_dto(self, card: dict[str, Any]) -> Optional[RawItemDTO]:
        project_id = card.get("id")
        title = (card.get("title") or "").strip()
        description = (card.get("description") or "").strip()
        if project_id is None or not (title or description):
            return None

        url = card.get("url") or ""
        if url and not url.startswith("http"):
            url = f"{FLRU_BASE_URL}{url}"

        return RawItemDTO(
            external_id=str(project_id),
            text=f"{title}\n{description}".strip(),
            url=url or None,
            published_at=card.get("published_at"),
            metadata={"source": "flru_projects", "price": card.get("price")},
        )

    @staticmethod
    def _to_int_or_none(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
