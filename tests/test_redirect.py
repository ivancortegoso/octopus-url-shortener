"""Covers GET /{code}."""

from fastapi.testclient import TestClient

from app.storage import InMemoryStorage


def _shorten(client: TestClient, url: str = "https://example.com/page") -> str:
    code: str = client.post("/shorten", json={"url": url}).json()["code"]
    return code


def test_following_a_code_redirects_to_the_original_url(client: TestClient) -> None:
    code = _shorten(client)

    response = client.get(f"/{code}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/page"


def test_an_unknown_code_returns_404(client: TestClient) -> None:
    response = client.get("/nothing", follow_redirects=False)

    assert response.status_code == 404


def test_following_a_code_records_the_click(
    client: TestClient, storage: InMemoryStorage
) -> None:
    code = _shorten(client)

    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"referer": "https://news.example", "user-agent": "pytest"},
    )

    assert len(storage.clicks) == 1
    click = storage.clicks[0]
    assert click.code == code
    assert click.referrer == "https://news.example"
    assert click.user_agent == "pytest"


def test_an_unknown_code_records_no_click(client: TestClient, storage: InMemoryStorage) -> None:
    client.get("/nothing", follow_redirects=False)

    assert storage.clicks == []
