"""BaseSourceAdapter: the contract every source (Telegram, future API/freelance
adapters) must implement so the pipeline can treat them uniformly.
"""
import datetime as dt
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class RawItemDTO:
    """Provider-agnostic shape for a single collected item.

    Every adapter, regardless of source type, returns a list of these —
    the pipeline (Stage 7) never needs to know which adapter produced them.
    """

    external_id: str
    text: str
    author_name: Optional[str] = None
    author_username: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[dt.datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseSourceAdapter(ABC):
    """One instance is bound to one Source row (see app.models.source.Source)."""

    @abstractmethod
    async def fetch_new_items(self) -> list[RawItemDTO]:
        """Return only items not previously returned by this adapter.

        Implementations own their own "last seen" bookkeeping (e.g. last
        processed message id) so repeated calls do not redeliver the same
        item — the pipeline still deduplicates independently as a second
        line of defense (DuplicateDetectionService), but adapters should
        not rely on that as their only safeguard.
        """
        raise NotImplementedError
