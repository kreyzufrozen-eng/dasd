"""Stage 7: IntervalScheduler — the minimal async background-job runner."""
import asyncio

import pytest

from app.workers.scheduler import IntervalScheduler


@pytest.mark.asyncio
async def test_scheduler_calls_tick_fn_repeatedly_until_stopped():
    scheduler = IntervalScheduler(interval_seconds=0.01)
    call_count = 0

    async def tick():
        nonlocal call_count
        call_count += 1
        if call_count >= 3:
            scheduler.stop()

    await asyncio.wait_for(scheduler.run_forever(tick), timeout=5)

    assert call_count == 3


@pytest.mark.asyncio
async def test_scheduler_survives_exception_in_tick_fn():
    scheduler = IntervalScheduler(interval_seconds=0.01)
    call_count = 0

    async def tick():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated failure")
        if call_count >= 2:
            scheduler.stop()

    # Must not raise despite the RuntimeError on the first tick.
    await asyncio.wait_for(scheduler.run_forever(tick), timeout=5)

    assert call_count == 2


@pytest.mark.asyncio
async def test_scheduler_stop_before_first_tick_prevents_run():
    scheduler = IntervalScheduler(interval_seconds=10)
    scheduler.stop()
    call_count = 0

    async def tick():
        nonlocal call_count
        call_count += 1

    await asyncio.wait_for(scheduler.run_forever(tick), timeout=5)

    assert call_count == 0
