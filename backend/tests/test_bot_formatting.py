"""Stage 8: message formatting for notifications and bot replies."""
from app.bot.formatting import (
    format_budget,
    format_lead_notification,
    format_lead_summary_line,
    format_services,
    format_signals,
    format_stats_message,
)
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source


def make_lead(**overrides) -> Lead:
    defaults = dict(
        id=1, lead_score=75, services=["web_design"], summary="Резюме",
        project_description="Описание", business_niche="beauty",
        budget_min=None, budget_max=None, currency=None,
        urgency="medium", positive_signals=[], negative_signals=[], status="new",
        intent_score=0, intent_signals=[], is_lead=True,
    )
    defaults.update(overrides)
    return Lead(**defaults)


def test_format_budget_range():
    lead = make_lead(budget_min=50000, budget_max=100000, currency="RUB")
    assert format_budget(lead) == "50000–100000 RUB"


def test_format_budget_single_value():
    lead = make_lead(budget_min=50000, budget_max=None, currency="RUB")
    assert format_budget(lead) == "50000 RUB"


def test_format_budget_not_mentioned():
    lead = make_lead(budget_min=None, budget_max=None)
    assert format_budget(lead) == "не указан"


def test_format_services_empty_and_nonempty():
    assert format_services([]) == "не указаны"
    assert format_services(["web_design", "landing_page"]) == "web_design, landing_page"


def test_format_signals_empty_and_nonempty():
    assert format_signals([]) == "—"
    assert format_signals(["a", "b"]) == "• a\n• b"


def test_format_lead_notification_normal_header():
    lead = make_lead(lead_score=70)
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="text", content_hash="h")
    source = Source(id=1, name="Test Channel", type="telegram")
    text = format_lead_notification(lead, raw_item, source)
    assert text.startswith("🔥 НОВЫЙ ЛИД")
    assert "Score: 70/100" in text
    assert "Test Channel" in text


def test_format_lead_notification_very_hot_header():
    lead = make_lead(lead_score=95)
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="text", content_hash="h")
    text = format_lead_notification(lead, raw_item, None)
    assert text.startswith("🔥🔥 ОЧЕНЬ ГОРЯЧИЙ ЛИД")
    assert "неизвестен" in text  # no source passed


def test_format_lead_summary_line_truncates_long_summary():
    lead = make_lead(summary="x" * 200)
    line = format_lead_summary_line(lead)
    assert line.startswith("#1 · 75/100")
    assert len(line) < 200


def test_format_stats_message_contains_all_numbers():
    text = format_stats_message(total=10, today=2, hot=3, converted=1)
    assert "10" in text and "2" in text and "3" in text and "1" in text
