"""Shared vocabularies used across models, schemas, and services.

These are plain Python (str) enums rather than native Postgres ENUM types:
columns are stored as VARCHAR and validated at the application boundary
(Pydantic schemas / service code). This keeps adding new values a pure
Python change with no migration required — the simpler, MVP-appropriate
choice over native DB enums, which need an ALTER TYPE migration per value.
"""
from enum import Enum


class SourceType(str, Enum):
    TELEGRAM = "telegram"
    API = "api"
    FREELANCE = "freelance"
    WEBSITE = "website"


class LeadStatus(str, Enum):
    NEW = "new"
    VIEWED = "viewed"
    CONTACTED = "contacted"
    INTERESTED = "interested"
    NEGOTIATION = "negotiation"
    CONVERTED = "converted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class UrgencyLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ComplexityLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EstimatedValue(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class KeywordCategory(str, Enum):
    DIRECT_INTENT = "direct_intent"
    SERVICE = "service"
    PROJECT_TYPE = "project_type"
    PROBLEM = "problem"
    TECHNOLOGY = "technology"
    # Signals of a business situation that will likely create a website
    # need soon, even though the author isn't asking for one yet — e.g.
    # a new venture launching Instagram-only, or an old site nobody has
    # touched. See Lead.intent_score / app/ai/prompts.py.
    HIDDEN_INTENT = "hidden_intent"
    # Words/phrases that REDUCE relevance rather than raise it (e.g.
    # "вакансия", "стажировка", "за отзыв") — per-profile only, matched
    # the same way as the others but subtracted rather than added when
    # scoring pre-filter confidence. See KeywordFilter.
    EXCLUSION = "exclusion"


class LeadFeedbackType(str, Enum):
    GOOD = "good"
    NOT_INTERESTING = "not_interesting"
    CLIENT = "client"
    ARCHIVED = "archived"


class OpportunityType(str, Enum):
    """Vocabulary only for now (SearchProfile.lead_types stores a subset of
    these) — the classification logic itself (per-profile AI matching) is
    Stage 3, not part of this Stage 1 foundation."""

    DIRECT_LEAD = "direct_lead"
    POTENTIAL_LEAD = "potential_lead"
    HIDDEN_OPPORTUNITY = "hidden_opportunity"


class LegalDocumentType(str, Enum):
    PRIVACY_POLICY = "privacy_policy"
    TERMS_OF_SERVICE = "terms_of_service"
    COOKIE_POLICY = "cookie_policy"


class TelegramTokenPurpose(str, Enum):
    """LOGIN: no session yet — a successful confirm either finds the
    existing User by telegram_id or creates a new one (auto-registration).
    LINK: caller already has a session (see app/api/deps.py's auth
    dependency) — a successful confirm sets telegram_id on *that* user
    instead of creating a new one."""

    LOGIN = "login"
    LINK = "link"


class TelegramTokenStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CONSUMED = "consumed"
    EXPIRED = "expired"


class SubscriptionStatus(str, Enum):
    """No payment provider exists yet (Этап 11 is architecture-only — see
    IMPLEMENTATION_PLAN.md §10) — ACTIVE is the only status that occurs in
    practice today (every user is auto-subscribed to the free plan on
    registration). The rest exist so a future billing integration has
    somewhere to put its state without another migration."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"
