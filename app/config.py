"""Application settings, read from the environment."""

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_CODE_LENGTH = 7
DEFAULT_RATE_LIMIT = 30
DEFAULT_RATE_WINDOW_SECONDS = 60


@dataclass(frozen=True, slots=True)
class Settings:
    """Values that change between environments."""

    base_url: str
    database_path: str
    code_length: int
    docs_enabled: bool
    rate_limit_per_window: int
    rate_limit_window_seconds: int


def _flag(name: str, *, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings(
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        database_path=os.getenv("DATABASE_PATH", "shortener.db"),
        code_length=int(os.getenv("CODE_LENGTH", str(DEFAULT_CODE_LENGTH))),
        # The generated documentation publishes the whole API surface, which is wanted in
        # development and is a decision to make deliberately anywhere else.
        docs_enabled=_flag("DOCS_ENABLED", default=True),
        rate_limit_per_window=int(os.getenv("RATE_LIMIT", str(DEFAULT_RATE_LIMIT))),
        rate_limit_window_seconds=int(
            os.getenv("RATE_LIMIT_WINDOW_SECONDS", str(DEFAULT_RATE_WINDOW_SECONDS))
        ),
    )
