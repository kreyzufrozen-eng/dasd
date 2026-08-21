"""Minimal in-process rate limiter for auth endpoints.

Deliberately not Redis-backed: this app runs as a single backend
container (see docker-compose.yml), so an in-memory counter is correct
and sufficient — same reasoning as app/workers/scheduler.py using a plain
asyncio loop instead of Celery. If the backend is ever scaled to multiple
replicas, swap this for a shared store; until then it'd be unused
complexity.
"""
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

# {key: [timestamps within the current window]}
_attempts: dict[str, list[float]] = defaultdict(list)


def rate_limit(key_prefix: str, max_attempts: int, window_seconds: int):
    """Returns a FastAPI dependency that 429s once `max_attempts` requests
    from the same client IP land within `window_seconds`."""

    async def _dependency(request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        key = f"{key_prefix}:{client_ip}"
        now = time.monotonic()

        window = [t for t in _attempts[key] if now - t < window_seconds]
        if len(window) >= max_attempts:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many attempts — try again later",
            )
        window.append(now)
        _attempts[key] = window

    return _dependency
