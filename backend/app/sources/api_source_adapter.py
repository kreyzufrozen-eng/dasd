"""ApiSourceAdapter: base for future sources reachable through an official,
permitted HTTP API (as opposed to scraping). Not wired to a concrete
provider yet — this is the extension point for Stage-6-and-later work like
a job-board API or a CRM webhook.
"""
from abc import abstractmethod
from typing import Optional

import httpx

from app.sources.base import BaseSourceAdapter, RawItemDTO


class ApiSourceAdapter(BaseSourceAdapter):
    """Subclass this for any source with an official REST/GraphQL API.

    Handles the shared plumbing (an httpx client, base URL, auth header)
    so concrete adapters only need to implement `_fetch_raw_items()` and
    map that provider's payload shape into RawItemDTO.
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def fetch_new_items(self) -> list[RawItemDTO]:
        async with httpx.AsyncClient(
            base_url=self.base_url, headers=self._headers(), timeout=self.timeout
        ) as client:
            return await self._fetch_raw_items(client)

    @abstractmethod
    async def _fetch_raw_items(self, client: httpx.AsyncClient) -> list[RawItemDTO]:
        raise NotImplementedError
