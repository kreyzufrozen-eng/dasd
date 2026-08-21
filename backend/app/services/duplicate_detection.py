"""DuplicateDetectionService: prevents creating more than one RawItem/Lead
for the same underlying message.

Two independent checks, per spec:
1. source_id + external_id — same source can't redeliver the same message.
2. content_hash — catches identical text reposted/forwarded across sources.

Text similarity (near-duplicate detection) is explicitly optional in the
spec and is NOT implemented here — flagged as a future extension point
rather than added now, to keep the MVP simple and avoid the false-positive
risk of fuzzy matching without real usage data to tune it against.
"""
import hashlib
import re

from app.repositories.raw_item_repository import RawItemRepository


def compute_content_hash(text: str) -> str:
    """Normalize whitespace only (case and punctuation preserved) so this
    catches exact-content reposts/forwards without conflating genuinely
    different messages that happen to differ only by case."""
    normalized = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class DuplicateDetectionService:
    def __init__(self, raw_item_repo: RawItemRepository) -> None:
        self.raw_item_repo = raw_item_repo

    async def is_duplicate(self, source_id: int, external_id: str, content_hash: str) -> bool:
        existing_by_id = await self.raw_item_repo.get_by_source_and_external_id(
            source_id, external_id
        )
        if existing_by_id is not None:
            return True

        existing_by_hash = await self.raw_item_repo.get_by_content_hash(content_hash)
        if existing_by_hash is not None:
            return True

        return False
