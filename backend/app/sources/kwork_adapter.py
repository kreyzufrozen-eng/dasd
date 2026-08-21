"""KworkProjectsAdapter: fetches new client project postings from
https://kwork.ru/projects — a public freelance-project marketplace.

Kwork has no official public API for project listings. This is a website
source (SourceType.WEBSITE), deliberately kept separate from
FreelanceSourceAdapter, which is reserved for platforms with an official
API/RSS — see app/sources/freelance_source_adapter.py.

Two things keep this responsible rather than a blind HTML scrape:
- kwork.ru/robots.txt does not disallow /projects.
- The page embeds its project listing server-side as a JSON payload
  (`window.stateData = {...}`) rather than requiring markup/CSS-selector
  scraping — we parse that JSON directly, which is far less fragile than
  parsing rendered HTML and touches nothing behind auth or paywalled.
"""
import datetime as dt
import json
from typing import Any, Optional

import httpx

from app.core.logging import get_logger
from app.models.source import Source
from app.sources.base import BaseSourceAdapter, RawItemDTO

logger = get_logger(__name__)

KWORK_PROJECTS_URL = "https://kwork.ru/projects"
STATE_VAR_MARKER = "window.stateData="
USER_AGENT = "ReadHunterBot/1.0 (+https://kwork.ru/projects public listing reader)"
DEFAULT_MAX_PAGES = 3
# Same policy as Telegram (see MAX_HISTORY_DAYS in telegram_adapter.py):
# never collect anything older than this, even on a fresh source.
MAX_AGE_DAYS = 5


class KworkProjectsAdapter(BaseSourceAdapter):
    def __init__(
        self, source: Source, max_pages: int = DEFAULT_MAX_PAGES, timeout: float = 20.0
    ) -> None:
        self.source = source
        self.max_pages = max_pages
        self.timeout = timeout

    async def fetch_new_items(self) -> list[RawItemDTO]:
        last_seen = self._to_int_or_none(self.source.last_external_id) or 0
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=MAX_AGE_DAYS)
        items: list[RawItemDTO] = []

        try:
            async with httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT}, timeout=self.timeout
            ) as client:
                for page in range(1, self.max_pages + 1):
                    url = KWORK_PROJECTS_URL if page == 1 else f"{KWORK_PROJECTS_URL}?page={page}"
                    response = await client.get(url)
                    response.raise_for_status()
                    projects = self._extract_projects(response.text)
                    if not projects:
                        break

                    stop_paging = False
                    for project in projects:
                        project_id = project.get("id")
                        if project_id is None or project_id <= last_seen:
                            stop_paging = True
                            continue
                        published_at = self._parse_datetime(project.get("date_create"))
                        if published_at is not None and published_at < cutoff:
                            # Listing is newest-first, so hitting one item
                            # past the cutoff means everything after it on
                            # this and later pages is even older — stop.
                            stop_paging = True
                            continue
                        dto = self._project_to_dto(project)
                        if dto is not None:
                            items.append(dto)

                    if stop_paging:
                        break
        except httpx.HTTPError as exc:
            logger.warning(
                "Kwork projects fetch failed: %s. Returning %d item(s) collected so far.",
                exc,
                len(items),
            )
        except Exception as exc:  # noqa: BLE001 - one bad page must not kill the poll cycle
            logger.exception("Unexpected error fetching Kwork projects: %s", exc)

        return items

    @staticmethod
    def _extract_projects(html: str) -> list[dict[str, Any]]:
        start_marker = html.find(STATE_VAR_MARKER)
        if start_marker == -1:
            return []
        start = start_marker + len(STATE_VAR_MARKER)
        end = KworkProjectsAdapter._find_json_object_end(html, start)
        if end is None:
            return []
        try:
            state = json.loads(html[start:end])
        except json.JSONDecodeError:
            logger.warning("Could not parse Kwork state JSON")
            return []
        return state.get("wantsListData", {}).get("pagination", {}).get("data", [])

    @staticmethod
    def _find_json_object_end(text: str, start: int) -> Optional[int]:
        """Balanced-brace scan (string/escape aware) from an opening `{`."""
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        return i + 1
        return None

    def _project_to_dto(self, project: dict[str, Any]) -> Optional[RawItemDTO]:
        project_id = project.get("id")
        title = (project.get("name") or "").strip()
        description = (project.get("description") or "").strip()
        if project_id is None or not (title or description):
            return None

        text = f"{title}\n{description}".strip()
        author = (project.get("user") or {}).get("username")

        return RawItemDTO(
            external_id=str(project_id),
            text=text,
            author_username=author,
            url=f"https://kwork.ru/projects/{project_id}",
            published_at=self._parse_datetime(project.get("date_create")),
            metadata={
                "source": "kwork_projects",
                "price_limit": project.get("priceLimit"),
                "possible_price_limit": project.get("possiblePriceLimit"),
                "category_id": project.get("category_id"),
            },
        )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[dt.datetime]:
        if not value:
            return None
        try:
            return dt.datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=dt.timezone.utc
            )
        except ValueError:
            return None

    @staticmethod
    def _to_int_or_none(value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
