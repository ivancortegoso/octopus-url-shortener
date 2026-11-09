"""Application settings, read from the environment."""

import os
from dataclasses import dataclass
from functools import lru_cache

DEFAULT_CODE_LENGTH = 7


@dataclass(frozen=True, slots=True)
class Settings:
    """Values that change between environments."""

    base_url: str
    database_path: str
    code_length: int


@lru_cache
def get_settings() -> Settings:
    return Settings(
        base_url=os.getenv("BASE_URL", "http://localhost:8000").rstrip("/"),
        database_path=os.getenv("DATABASE_PATH", "shortener.db"),
        code_length=int(os.getenv("CODE_LENGTH", str(DEFAULT_CODE_LENGTH))),
    )
