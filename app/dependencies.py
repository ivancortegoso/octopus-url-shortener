"""Wiring between the application and the collaborators it needs."""

from functools import lru_cache

from app.config import get_settings
from app.rate_limiting import SlidingWindowRateLimiter
from app.storage import SqliteStorage, Storage


@lru_cache
def get_storage() -> Storage:
    """Return the storage the running application uses.

    Declared as a FastAPI dependency so tests can swap in the in-memory implementation
    without touching the routes.
    """
    return SqliteStorage(get_settings().database_path)


@lru_cache
def get_rate_limiter() -> SlidingWindowRateLimiter:
    """Return the limiter guarding link creation, shared across requests."""
    settings = get_settings()
    return SlidingWindowRateLimiter(
        limit=settings.rate_limit_per_window,
        window_seconds=settings.rate_limit_window_seconds,
    )
