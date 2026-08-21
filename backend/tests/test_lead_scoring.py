"""Stage 4: LeadScoringService — configurable weights, clamping, edge cases."""
import datetime as dt

import pytest

from app.core.scoring_config import ScoringWeights
from app.services.lead_scoring import LeadScoringInput, LeadScoringService


@pytest.fixture
def service() -> LeadScoringService:
    return LeadScoringService()


def test_all_zero_signals_scores_zero(service):
    result = service.calculate_score(LeadScoringInput())
    assert result.score == 0
    assert result.raw_score == 0
    assert result.breakdown == {}


def test_strong_positive_lead_scores_high(service):
    signals = LeadScoringInput(
        direct_search=True,
        has_concrete_description=True,
        business_niche="стоматология",
        budget_mentioned=True,
        high_urgency=True,
        matches_offered_services=True,
        has_contact_method=True,
    )
    result = service.calculate_score(signals)
    # 30+15+10+15+10+10+5 = 95
    assert result.raw_score == 95
    assert result.score == 95
    assert result.breakdown["direct_intent"] == 30


def test_fresh_lead_bonus_applied_within_window(service):
    now = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.timezone.utc)
    published_at = now - dt.timedelta(hours=1)
    signals = LeadScoringInput(direct_search=True, published_at=published_at)
    result = service.calculate_score(signals, now=now)
    assert "fresh_lead" in result.breakdown
    assert result.score == 30 + 5


def test_fresh_lead_bonus_not_applied_outside_window(service):
    now = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.timezone.utc)
    published_at = now - dt.timedelta(days=10)
    signals = LeadScoringInput(direct_search=True, published_at=published_at)
    result = service.calculate_score(signals, now=now)
    assert "fresh_lead" not in result.breakdown
    assert result.score == 30


def test_negative_signals_reduce_score(service):
    signals = LeadScoringInput(direct_search=True, author_seeking_job=True)
    result = service.calculate_score(signals)
    assert result.raw_score == 30 - 50
    assert result.raw_score == -20
    assert result.score == 0  # clamped to score_min


def test_score_never_exceeds_max(service):
    signals = LeadScoringInput(
        direct_search=True,
        has_concrete_description=True,
        business_niche="ecommerce",
        budget_mentioned=True,
        high_urgency=True,
        matches_offered_services=True,
        has_contact_method=True,
        published_at=dt.datetime.now(dt.timezone.utc),
    )
    result = service.calculate_score(signals)
    assert result.raw_score == 100  # 95 + 5 fresh
    assert result.score == 100
    assert result.score <= 100


def test_score_never_negative_even_with_all_negative_signals(service):
    signals = LeadScoringInput(
        author_seeking_job=True,
        advertising_own_services=True,
        site_recommendation=True,
        not_commercial_need=True,
    )
    result = service.calculate_score(signals)
    assert result.raw_score == -50 - 50 - 40 - 40
    assert result.score == 0


def test_is_very_hot_threshold(service):
    signals = LeadScoringInput(
        direct_search=True,
        has_concrete_description=True,
        business_niche="x",
        budget_mentioned=True,
        high_urgency=True,
        matches_offered_services=True,
    )
    # 30+15+10+15+10+10 = 90
    result = service.calculate_score(signals)
    assert result.score == 90
    assert result.is_very_hot is True


def test_is_very_hot_false_below_threshold(service):
    signals = LeadScoringInput(direct_search=True, has_concrete_description=True)
    result = service.calculate_score(signals)
    assert result.score == 45
    assert result.is_very_hot is False


def test_weights_are_configurable():
    custom_weights = ScoringWeights(direct_intent=50, score_max=100)
    custom_service = LeadScoringService(weights=custom_weights)
    signals = LeadScoringInput(direct_search=True)
    result = custom_service.calculate_score(signals)
    assert result.score == 50


def test_business_niche_none_does_not_trigger_bonus(service):
    signals = LeadScoringInput(business_niche=None)
    result = service.calculate_score(signals)
    assert "business_niche_specified" not in result.breakdown


def test_business_niche_empty_string_does_not_trigger_bonus(service):
    signals = LeadScoringInput(business_niche="")
    result = service.calculate_score(signals)
    assert "business_niche_specified" not in result.breakdown


def test_naive_datetime_published_at_is_handled(service):
    # published_at without tzinfo shouldn't raise — treated as UTC.
    now = dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.timezone.utc)
    naive_published = dt.datetime(2026, 8, 15, 11, 0)  # no tzinfo
    signals = LeadScoringInput(published_at=naive_published)
    result = service.calculate_score(signals, now=now)
    assert "fresh_lead" in result.breakdown
