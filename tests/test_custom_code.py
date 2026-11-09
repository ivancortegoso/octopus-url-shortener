"""Covers the optional caller-chosen short code."""

from fastapi.testclient import TestClient


def test_a_requested_code_is_used_verbatim(client: TestClient) -> None:
    response = client.post(
        "/shorten", json={"url": "https://example.com", "code": "black-friday"}
    )

    assert response.status_code == 201
    assert response.json()["code"] == "black-friday"
    assert client.get("/black-friday", follow_redirects=False).status_code == 302


def test_a_taken_code_is_refused_with_409(client: TestClient) -> None:
    client.post("/shorten", json={"url": "https://example.com", "code": "spring-sale"})

    response = client.post("/shorten", json={"url": "https://other.example", "code": "spring-sale"})

    assert response.status_code == 409


def test_a_reserved_code_is_refused_with_409(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "https://example.com", "code": "docs"})

    assert response.status_code == 409


def test_a_code_with_unsupported_characters_is_refused_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "https://example.com", "code": "no spaces"})

    assert response.status_code == 400


def test_a_code_that_is_too_short_is_refused_with_400(client: TestClient) -> None:
    response = client.post("/shorten", json={"url": "https://example.com", "code": "ab"})

    assert response.status_code == 400
