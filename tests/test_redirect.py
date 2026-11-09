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
    assert client.get("/nothing", follow_redirects=False).status_code == 404


def test_following_a_code_records_the_click(client: TestClient, storage: InMemoryStorage) -> None:
    code = _shorten(client)

    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={
            "referer": "https://news.example",
            "user-agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
            "cf-ipcountry": "es",
        },
    )

    assert len(storage.clicks) == 1
    click = storage.clicks[0]
    assert click.code == code
    assert click.referrer == "https://news.example"
    assert click.country == "ES"
    assert click.device == "mobile"


def test_a_click_without_an_edge_country_records_none(
    client: TestClient, storage: InMemoryStorage
) -> None:
    code = _shorten(client)

    client.get(f"/{code}", follow_redirects=False)

    assert storage.clicks[0].country is None


def test_an_unknown_code_records_no_click(client: TestClient, storage: InMemoryStorage) -> None:
    client.get("/nothing", follow_redirects=False)

    assert storage.clicks == []


def test_a_browser_sees_a_page_for_an_unknown_code(client: TestClient) -> None:
    response = client.get(
        "/nothing", follow_redirects=False, headers={"accept": "text/html,*/*;q=0.8"}
    )

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert "does not exist" in response.text


def test_a_program_still_gets_json_for_an_unknown_code(client: TestClient) -> None:
    response = client.get("/nothing", follow_redirects=False, headers={"accept": "*/*"})

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown short code."}
