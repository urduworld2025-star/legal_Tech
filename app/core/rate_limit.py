"""A tiny in-process sliding-window rate limiter.

`POST /auth/register` is this app's first public, unauthenticated write endpoint, so
it needs *some* abuse guard. The production deployment runs a single uvicorn worker
(see README's shared-hosting deployment notes), so in-process state is sufficient -
no Redis/memcached dependency needed for this.
"""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_WINDOW_SECONDS = 3600
_MAX_REGISTRATIONS_PER_WINDOW = 5

_registration_hits: dict[str, deque[float]] = defaultdict(deque)


def enforce_registration_rate_limit(request: Request) -> None:
    client_host = request.client.host if request.client else "unknown"
    now = time.monotonic()
    hits = _registration_hits[client_host]
    while hits and now - hits[0] > _WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= _MAX_REGISTRATIONS_PER_WINDOW:
        raise HTTPException(status_code=429, detail="Too many registration attempts. Try again later.")
    hits.append(now)


def reset() -> None:
    """Test-only hook - clears all rate-limit state between tests, since
    `_registration_hits` is module-level and would otherwise leak across the whole
    pytest session (every TestClient request shares the same client host)."""
    _registration_hits.clear()
