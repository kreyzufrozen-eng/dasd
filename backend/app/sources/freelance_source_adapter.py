"""FreelanceSourceAdapter: extension point for freelance-platform sources.

Deliberately NOT implemented with scraping or any anti-bot bypass — per
project rules, freelance-board integrations are only added here once a
specific platform offers a permitted API/RSS/webhook to pull listings
from legitimately. Until then this stays an interface so the rest of the
system (models, pipeline, scoring) already knows how to consume such a
source the moment one is added.
"""
from app.sources.api_source_adapter import ApiSourceAdapter


class FreelanceSourceAdapter(ApiSourceAdapter):
    """Subclass per platform once that platform's official API/feed is
    identified (e.g. an RSS feed of public postings, or a partner API).
    Do not implement HTML scraping here."""
