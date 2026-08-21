"""poll_with_backoff: retries dispatcher.start_polling() with exponential
backoff on TelegramNetworkError instead of letting docker-compose's
`restart: unless-stopped` crash-loop the whole container during a Telegram
outage (see app/bot/run_bot.py module docstring)."""
import pytest
from aiogram.exceptions import TelegramNetworkError, TelegramUnauthorizedError

from app.bot import run_bot
from app.bot.run_bot import poll_with_backoff


def _network_error() -> TelegramNetworkError:
    return TelegramNetworkError(method=None, message="Request timeout error")


@pytest.mark.asyncio
async def test_retries_on_network_error_then_succeeds(monkeypatch):
    sleeps = []
    async def fake_sleep(s):
        sleeps.append(s)
    monkeypatch.setattr(run_bot.asyncio, "sleep", fake_sleep)

    calls = 0

    async def start_polling():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise _network_error()

    await poll_with_backoff(start_polling)

    assert calls == 3
    assert sleeps == [5, 10]  # INITIAL_BACKOFF_SECONDS then doubled


@pytest.mark.asyncio
async def test_backoff_caps_at_max(monkeypatch):
    sleeps = []
    async def fake_sleep(s):
        sleeps.append(s)
    monkeypatch.setattr(run_bot.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(run_bot, "MAX_BACKOFF_SECONDS", 15)

    calls = 0

    async def start_polling():
        nonlocal calls
        calls += 1
        if calls < 5:
            raise _network_error()

    await poll_with_backoff(start_polling)

    assert sleeps == [5, 10, 15, 15]  # capped once it would exceed MAX_BACKOFF_SECONDS


@pytest.mark.asyncio
async def test_backoff_resets_after_a_long_running_attempt(monkeypatch):
    sleeps = []
    async def fake_sleep(s):
        sleeps.append(s)
    monkeypatch.setattr(run_bot.asyncio, "sleep", fake_sleep)

    # Fake clock consumed in order: [attempt1 start, attempt1 fail,
    # attempt2 start, attempt2 fail, attempt3 start]. Attempt 2 "runs" for
    # 100s (well past BACKOFF_RESET_AFTER_SECONDS=60) before failing, so its
    # backoff should reset to INITIAL_BACKOFF_SECONDS instead of doubling.
    clock = iter([0, 0, 100, 200, 300])
    monkeypatch.setattr(run_bot.time, "monotonic", lambda: next(clock))

    calls = 0

    async def start_polling():
        nonlocal calls
        calls += 1
        if calls == 3:
            return  # normal shutdown on the final attempt
        raise _network_error()

    await poll_with_backoff(start_polling)

    assert calls == 3
    # Both sleeps are the initial value: attempt 1 fails instantly (backoff
    # not yet reset-eligible, but it's already at its floor) then doubles to
    # 10; attempt 2's 100s runtime resets it back to 5 before that sleep.
    assert sleeps == [5, 5]


@pytest.mark.asyncio
async def test_non_network_telegram_errors_are_not_retried(monkeypatch):
    async def fail_sleep(s):
        pytest.fail("should not sleep")
    monkeypatch.setattr(run_bot.asyncio, "sleep", fail_sleep)

    async def start_polling():
        raise TelegramUnauthorizedError(method=None, message="Unauthorized")

    with pytest.raises(TelegramUnauthorizedError):
        await poll_with_backoff(start_polling)
