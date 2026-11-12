from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from fastapi import Depends, HTTPException, status

from app.core.deps import get_current_user
from app.models import User

# Simple in-memory sliding-window limiter keyed by "bucket:user_id".
# This is adequate for a single-process server; a multi-worker deployment
# would move this counter into Redis.
_WINDOW_SECONDS = 60.0
_HITS: dict[str, deque[float]] = defaultdict(deque)


def reset() -> None:
    """Clear all counters (used by the test suite)."""
    _HITS.clear()


def check(key: str, limit: int, window: float = _WINDOW_SECONDS) -> None:
    now = time.monotonic()
    hits = _HITS[key]
    while hits and now - hits[0] > window:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait a moment and try again.",
        )
    hits.append(now)


def rate_limited(bucket: str, limit: int, window: float = _WINDOW_SECONDS) -> Callable[..., None]:
    """Build a FastAPI dependency that caps each user to *limit* calls per *window*."""

    def dependency(user: User = Depends(get_current_user)) -> None:
        check(f"{bucket}:{user.id}", limit, window)

    return dependency
