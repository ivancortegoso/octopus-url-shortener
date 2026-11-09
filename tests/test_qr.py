"""Covers GET /qr/{code}."""

from fastapi.testclient import TestClient

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def test_a_known_code_renders_a_png(client: TestClient) -> None:
    code = client.post("/shorten", json={"url": "https://example.com"}).json()["code"]

    response = client.get(f"/qr/{code}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(PNG_SIGNATURE)


def test_an_unknown_code_returns_404(client: TestClient) -> None:
    assert client.get("/qr/nothing").status_code == 404
