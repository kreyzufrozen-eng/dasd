"""Lead scoring weights — kept separate from business logic so they can be
tuned without touching LeadScoringService itself.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringWeights:
    # --- Positive signals ---
    direct_intent: int = 30          # author explicitly looking for a contractor
    concrete_project_description: int = 15
    business_niche_specified: int = 10
    budget_mentioned: int = 15
    high_urgency: int = 10
    matches_offered_services: int = 10
    has_contact_method: int = 5
    fresh_lead: int = 5              # published recently

    # --- Negative signals ---
    author_seeking_job: int = -50
    advertising_own_services: int = -50
    site_recommendation: int = -40
    not_commercial_need: int = -40

    # --- Bounds ---
    score_min: int = 0
    score_max: int = 100

    # How fresh (hours) counts as "fresh_lead"
    fresh_lead_max_age_hours: int = 48


DEFAULT_SCORING_WEIGHTS = ScoringWeights()
