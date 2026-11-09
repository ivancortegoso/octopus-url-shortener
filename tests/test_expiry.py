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


def _expired_link(code: str = "expired", fallback: str | None = None) -> Link:
    """A link already past its expiry. Written straight to storage, because the API
    refuses to create one."""
    return Link(
        code=code,
        url="https://example.com",
        label=None,
        created_at=datetime.now(UTC) - timedelta(days=2),
        expires_at=datetime.now(UTC) - timedelta(days=1),
        fallback_url=fallback,
    )


def test_an_expired_link_without_a_fallback_answers_410(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(_expired_link())

    assert client.get("/expired", follow_redirects=False).status_code == 410


def test_an_expired_link_sends_visitors_to_its_fallback(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(_expired_link(fallback="https://example.com/tariffs"))

    response = client.get("/expired", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/tariffs"


def test_clicks_after_expiry_are_counted_apart_from_the_total(
    client: TestClient, storage: InMemoryStorage
) -> None:
    # Someone still holding a printed copy is worth knowing about, so the click is kept —
    # just not mixed into the figure that says how the campaign performed.
    storage.add_link(_expired_link())
    client.get("/expired", follow_redirects=False)

    body = client.get("/stats/expired").json()

    assert body["expired_clicks"] == 1
    assert body["total_clicks"] == 0


def test_the_statistics_report_an_expired_link_as_expired(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(_expired_link(fallback="https://example.com/tariffs"))

    body = client.get("/stats/expired").json()

    assert body["is_expired"] is True
    assert body["fallback_url"] == "https://example.com/tariffs"


def test_a_fallback_inside_a_private_network_is_refused(client: TestClient) -> None:
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    response = client.post(
        "/shorten",
        json={
            "url": "https://example.com",
            "expires_at": future,
            "fallback_url": "http://10.0.0.5/admin",
        },
    )

    assert response.status_code == 400


def test_a_browser_sees_a_page_when_a_link_has_expired(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(_expired_link())

    response = client.get(
        "/expired", follow_redirects=False, headers={"accept": "text/html,*/*;q=0.8"}
    )

    assert response.status_code == 410
    assert response.headers["content-type"].startswith("text/html")
    assert "has expired" in response.text


def test_a_program_still_gets_json_when_a_link_has_expired(
    client: TestClient, storage: InMemoryStorage
) -> None:
    storage.add_link(_expired_link())

    response = client.get("/expired", follow_redirects=False, headers={"accept": "*/*"})

    assert response.status_code == 410
    assert response.json() == {"detail": "This link has expired."}
