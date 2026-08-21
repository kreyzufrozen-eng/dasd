"""IntervalScheduler: the simplest thing that could work for Stage 1 of
background jobs — a single asyncio loop calling a tick function on a fixed
interval.

Deliberately minimal (no persistence, no distributed workers, no retries
across process restarts) so it's obvious how to replace it later with
Arq/Celery + Redis without touching any business logic: everything this
calls (collection cycle, pipeline processing) is a plain async function
that doesn't know or care what's scheduling it.
"""
import asyncio
from typing import Awaitable, Callable

from app.core.logging import get_logger

logger = get_logger(__name__)

TickFn = Callable[[], Awaitable[None]]


class IntervalScheduler:
    def __init__(self, interval_seconds: int) -> None:
        self.interval_seconds = interval_seconds
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    async def run_forever(self, tick_fn: TickFn) -> None:
        while not self._stop_event.is_set():
            try:
                await tick_fn()
            except Exception:  # noqa: BLE001 - a single bad tick must not kill the loop
                logger.exception("Unhandled error in scheduled tick, will retry next interval")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=self.interval_seconds)
            except asyncio.TimeoutError:
                pass  # normal: interval elapsed without a stop request
