"""Shared test fixtures."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_storage
from app.main import app
from app.storage import InMemoryStorage


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def client(storage: InMemoryStorage) -> Iterator[TestClient]:
    """A client whose application writes to the in-memory storage."""
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()
