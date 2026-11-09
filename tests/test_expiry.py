"""Covers links that stop resolving at a chosen moment."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.domain import Link
from app.storage import InMemoryStorage


def test_an_expiry_in_the_past_is_refused_with_400(client: TestClient) -> None:
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()

    response = client.post(
        "/shorten", json={"url": "https://example.com", "expires_at": past}
    )

    assert response.status_code == 400


def test_an_expiry_in_the_future_is_accepted_and_returned(client: TestClient) -> None:
    future = (datetime.now(UTC) + timedelta(days=7)).isoformat()

    response = client.post(
        "/shorten", json={"url": "https://example.com", "expires_at": future}
    )

    assert response.status_code == 201
    assert response.json()["expires_at"] is not None


def test_a_link_still_within_its_window_resolves(client: TestClient) -> None:
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    code = client.post(
        "/shorten", json={"url": "https://example.com", "expires_at": future}
    ).json()["code"]

    assert client.get(f"/{code}", follow_redirects=False).status_code == 302


def test_an_expired_link_answers_410_and_records_no_click(
    client: TestClient, storage: InMemoryStorage
) -> None:
    # Written straight to storage: the API refuses to create a link already expired.
    storage.add_link(
        Link(
            code="expired",
            url="https://example.com",
            label=None,
            created_at=datetime.now(UTC) - timedelta(days=2),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )

    response = client.get("/expired", follow_redirects=False)

    assert response.status_code == 410
    assert storage.clicks == []


def test_the_statistics_report_an_expired_link_as_expired(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(
        Link(
            code="expired",
            url="https://example.com",
            label=None,
            created_at=datetime.now(UTC) - timedelta(days=2),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
    )

    body = client.get("/stats/expired").json()

    assert body["is_expired"] is True
