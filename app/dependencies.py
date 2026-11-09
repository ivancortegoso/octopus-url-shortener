"""Wiring between the application and its storage."""

from functools import lru_cache

from app.config import get_settings
from app.storage import SqliteStorage, Storage


@lru_cache
def get_storage() -> Storage:
    """Return the storage the running application uses.

    Declared as a FastAPI dependency so tests can swap in the in-memory implementation
    without touching the routes.
    """
    return SqliteStorage(get_settings().database_path)
