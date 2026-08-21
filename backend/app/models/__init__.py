"""ORM models package.

Every model must be imported here so it registers on Base.metadata — this
is what alembic/env.py relies on for autogenerate, and what
`Base.metadata.create_all()` relies on in tests.
"""
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.keyword import Keyword  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.lead_feedback import LeadFeedback  # noqa: F401
from app.models.legal_document import LegalDocument  # noqa: F401
from app.models.raw_item import RawItem  # noqa: F401
from app.models.search_profile import SearchProfile  # noqa: F401
from app.models.search_profile_keyword import SearchProfileKeyword  # noqa: F401
from app.models.search_profile_source import SearchProfileSource  # noqa: F401
from app.models.source import Source  # noqa: F401
from app.models.subscription import Subscription  # noqa: F401
from app.models.subscription_plan import SubscriptionPlan  # noqa: F401
from app.models.telegram_login_token import TelegramLoginToken  # noqa: F401
from app.models.usage_counter import UsageCounter  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.user_legal_acceptance import UserLegalAcceptance  # noqa: F401

__all__ = [
    "Source",
    "RawItem",
    "Lead",
    "LeadFeedback",
    "Keyword",
    "User",
    "SearchProfile",
    "SearchProfileSource",
    "SearchProfileKeyword",
    "SubscriptionPlan",
    "Subscription",
    "UsageCounter",
    "TelegramLoginToken",
    "LegalDocument",
    "UserLegalAcceptance",
    "AuditLog",
]
