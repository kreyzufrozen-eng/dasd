"""LeadScoringService: turns AI-analysis signals into a 0-100 lead score.

Deliberately decoupled from the AIProvider's Pydantic schema (Stage 5) —
takes a plain LeadScoringInput so this service is independently testable
and the AI schema can evolve without touching scoring logic. The pipeline
(Stage 7) is responsible for mapping AI output -> LeadScoringInput.
"""
import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

from app.core.scoring_config import DEFAULT_SCORING_WEIGHTS, ScoringWeights


@dataclass(frozen=True)
class LeadScoringInput:
    # Positive signals
    direct_search: bool = False
    has_concrete_description: bool = False
    business_niche: Optional[str] = None
    budget_mentioned: bool = False
    high_urgency: bool = False
    matches_offered_services: bool = False
    has_contact_method: bool = False
    published_at: Optional[dt.datetime] = None

    # Negative signals
    author_seeking_job: bool = False
    advertising_own_services: bool = False
    site_recommendation: bool = False
    not_commercial_need: bool = False


@dataclass(frozen=True)
class LeadScoringResult:
    score: int  # clamped to [score_min, score_max]
    raw_score: int  # pre-clamp, can be negative or exceed max
    breakdown: dict = field(default_factory=dict)  # signal name -> points applied

    @property
    def is_very_hot(self) -> bool:
        return self.score >= 90


class LeadScoringService:
    def __init__(self, weights: ScoringWeights = DEFAULT_SCORING_WEIGHTS) -> None:
        self.weights = weights

    def _is_fresh(self, published_at: Optional[dt.datetime], now: dt.datetime) -> bool:
        if published_at is None:
            return False
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=dt.timezone.utc)
        age = now - published_at
        return age <= dt.timedelta(hours=self.weights.fresh_lead_max_age_hours)

    def calculate_score(
        self, signals: LeadScoringInput, now: Optional[dt.datetime] = None
    ) -> LeadScoringResult:
        now = now or dt.datetime.now(dt.timezone.utc)
        w = self.weights
        breakdown: dict = {}

        def apply(name: str, condition: bool, points: int) -> None:
            if condition:
                breakdown[name] = points

        apply("direct_intent", signals.direct_search, w.direct_intent)
        apply("concrete_project_description", signals.has_concrete_description, w.concrete_project_description)
        apply("business_niche_specified", bool(signals.business_niche), w.business_niche_specified)
        apply("budget_mentioned", signals.budget_mentioned, w.budget_mentioned)
        apply("high_urgency", signals.high_urgency, w.high_urgency)
        apply("matches_offered_services", signals.matches_offered_services, w.matches_offered_services)
        apply("has_contact_method", signals.has_contact_method, w.has_contact_method)
        apply("fresh_lead", self._is_fresh(signals.published_at, now), w.fresh_lead)

        apply("author_seeking_job", signals.author_seeking_job, w.author_seeking_job)
        apply("advertising_own_services", signals.advertising_own_services, w.advertising_own_services)
        apply("site_recommendation", signals.site_recommendation, w.site_recommendation)
        apply("not_commercial_need", signals.not_commercial_need, w.not_commercial_need)

        raw_score = sum(breakdown.values())
        clamped = max(w.score_min, min(w.score_max, raw_score))

        return LeadScoringResult(score=clamped, raw_score=raw_score, breakdown=breakdown)
