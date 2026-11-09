"""Covers POST /shorten."""

from fastapi.testclient import TestClient

from app.storage import InMemoryStorage


def test_shortening_a_url_returns_a_code_and_a_short_url(
    client: TestClient, storage: InMemoryStorage
) -> None:
    response = client.post("/shorten", json={"url": "https://example.com", "label": "home"})

    assert response.status_code == 201
    body = response.json()
    assert body["short_url"].endswith(body["code"])
    assert storage.links[body["code"]].url == "https://example.com/"
    assert storage.links[body["code"]].label == "home"


def test_the_label_is_optional(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "https://example.com"})

    assert response.status_code == 201


def test_an_invalid_url_is_rejected_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "not-a-url"})

    assert response.status_code == 400


def test_a_non_http_scheme_is_rejected_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "ftp://example.com/file"})

    assert response.status_code == 400


def test_two_requests_for_the_same_url_get_different_codes(client: TestClient) -> None:
    first = client.post("/shorten", json={"url": "https://example.com"}).json()
    second = client.post("/shorten", json={"url": "https://example.com"}).json()

    assert first["code"] != second["code"]


def test_a_private_destination_is_refused_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "http://169.254.169.254/latest/meta-data/"})

    assert response.status_code == 400


def test_a_destination_pointing_at_the_service_is_refused_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "http://localhost:8000/docs"})

    assert response.status_code == 400
