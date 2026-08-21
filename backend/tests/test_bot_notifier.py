"""Stage 8: LeadNotifier — threshold gating and failure isolation."""
from unittest.mock import AsyncMock

import pytest

from app.bot.notifier import LeadNotifier
from app.models.lead import Lead
from app.models.raw_item import RawItem
from app.models.source import Source


def make_lead(score: int) -> Lead:
    return Lead(
        id=1, lead_score=score, services=[], summary="s", positive_signals=[], negative_signals=[],
        intent_score=0, intent_signals=[], is_lead=True,
    )


@pytest.mark.asyncio
async def test_below_threshold_does_not_send():
    bot = AsyncMock()
    notifier = LeadNotifier(bot)
    lead = make_lead(score=40)
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="t", content_hash="h")

    sent = await notifier.notify_if_qualifying(lead, raw_item, None, threshold=60, chat_id="123")

    assert sent is False
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_above_threshold_sends_with_expected_content():
    bot = AsyncMock()
    notifier = LeadNotifier(bot)
    lead = make_lead(score=80)
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="t", content_hash="h", url="https://t.me/x/1")
    source = Source(id=1, name="Chan", type="telegram")

    sent = await notifier.notify_if_qualifying(lead, raw_item, source, threshold=60, chat_id="123")

    assert sent is True
    bot.send_message.assert_awaited_once()
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs["chat_id"] == "123"
    assert "Score: 80/100" in kwargs["text"]
    assert kwargs["reply_markup"] is not None


@pytest.mark.asyncio
async def test_send_failure_is_caught_and_returns_false():
    bot = AsyncMock()
    bot.send_message.side_effect = RuntimeError("network error")
    notifier = LeadNotifier(bot)
    lead = make_lead(score=80)
    raw_item = RawItem(id=1, source_id=1, external_id="1", text="t", content_hash="h")

    sent = await notifier.notify_if_qualifying(lead, raw_item, None, threshold=60, chat_id="123")  # must not raise

    assert sent is False
