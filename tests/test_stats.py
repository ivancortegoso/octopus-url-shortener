"""Covers GET /stats/{code}."""

from fastapi.testclient import TestClient


def test_stats_report_the_url_and_the_click_total(client: TestClient) -> None:
    code = client.post(
        "/shorten", json={"url": "https://example.com/page", "label": "home"}
    ).json()["code"]
    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False, headers={"referer": "https://news.example"})

    body = client.get(f"/stats/{code}").json()

    assert body["url"] == "https://example.com/page"
    assert body["label"] == "home"
    assert body["total_clicks"] == 3
    assert body["top_referrers"] == {"https://news.example": 3}
    assert body["last_clicked_at"] is not None
    assert sum(body["clicks_per_day"].values()) == 3


def test_stats_for_an_unused_link_report_no_clicks(client: TestClient) -> None:
    code = client.post("/shorten", json={"url": "https://example.com"}).json()["code"]

    body = client.get(f"/stats/{code}").json()

    assert body["total_clicks"] == 0
    assert body["last_clicked_at"] is None
    assert body["clicks_per_day"] == {}


def test_stats_for_an_unknown_code_return_404(client: TestClient) -> None:
    assert client.get("/stats/nothing").status_code == 404
