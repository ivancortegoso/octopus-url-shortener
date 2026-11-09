"""Covers the two health checks, which answer different questions."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_storage
from app.main import app
from app.storage import InMemoryStorage


class UnreachableStorage(InMemoryStorage):
    """Stands in for a database that has stopped answering."""

    def check_reachable(self) -> None:
        raise OSError("unable to open database file")


@pytest.fixture
def unreachable() -> Iterator[TestClient]:
    app.dependency_overrides[get_storage] = UnreachableStorage
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_readiness_reports_a_reachable_database(client: TestClient) -> None:
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "reachable"}


def test_readiness_reports_503_when_the_database_is_unreachable(
    unreachable: TestClient,
) -> None:
    response = unreachable.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unreachable"}


def test_liveness_stays_up_even_when_the_database_is_unreachable(
    unreachable: TestClient,
) -> None:
    # The whole point: a database problem must not be answered by restarting the process.
    response = unreachable.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
