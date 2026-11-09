"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_rate_limiter, get_storage
from app.main import app
from app.rate_limiting import SlidingWindowRateLimiter
from app.storage import InMemoryStorage

# The running service shares one limiter across requests, which is the point of it. Tests
# get their own so one test cannot spend another's allowance; the limiter's own behaviour
# is covered directly in test_rate_limiting.
TEST_ALLOWANCE = 10_000


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def client(storage: InMemoryStorage) -> Iterator[TestClient]:
    """A client whose application writes to the in-memory storage."""
    limiter = SlidingWindowRateLimiter(limit=TEST_ALLOWANCE, window_seconds=60)
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    yield TestClient(app)
    app.dependency_overrides.clear()
