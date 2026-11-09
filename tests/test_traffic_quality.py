"""Covers how automated traffic and the arrival channel are recorded."""

from fastapi.testclient import TestClient

from app.storage import InMemoryStorage

PREVIEW_AGENTS = [
    "Slackbot-LinkExpanding 1.0",
    "WhatsApp/2.23",
    "facebookexternalhit/1.1",
    "TelegramBot (like TwitterBot)",
    "Googlebot/2.1",
]


def _shorten(client: TestClient) -> str:
    code: str = client.post("/shorten", json={"url": "https://example.com"}).json()["code"]
    return code


def test_a_head_request_is_recorded_as_automated(
    client: TestClient, storage: InMemoryStorage
) -> None:
    code = _shorten(client)

    client.head(f"/{code}", follow_redirects=False)

    assert storage.clicks[0].is_bot is True


def test_chat_preview_fetches_are_recorded_as_automated(
    client: TestClient, storage: InMemoryStorage
) -> None:
    code = _shorten(client)

    for agent in PREVIEW_AGENTS:
        client.get(f"/{code}", follow_redirects=False, headers={"user-agent": agent})

    assert all(click.is_bot for click in storage.clicks)


def test_automated_traffic_is_reported_apart_from_the_total(client: TestClient) -> None:
    code = _shorten(client)
    client.get(f"/{code}", follow_redirects=False, headers={"user-agent": "Slackbot 1.0"})
    client.get(
        f"/{code}",
        follow_redirects=False,
        headers={"user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
    )

    body = client.get(f"/stats/{code}").json()

    assert body["total_clicks"] == 1
    assert body["bot_clicks"] == 1


def test_a_scan_is_distinguished_from_a_tap(client: TestClient) -> None:
    code = _shorten(client)
    client.get(f"/{code}?ch=qr", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)
    client.get(f"/{code}", follow_redirects=False)

    body = client.get(f"/stats/{code}").json()

    assert body["clicks_by_channel"] == {"link": 2, "qr": 1}


def test_the_channel_marker_is_not_passed_to_the_destination(client: TestClient) -> None:
    code = _shorten(client)

    response = client.get(f"/{code}?ch=qr", follow_redirects=False)

    assert response.headers["location"] == "https://example.com/"


def test_tracking_parameters_are_carried_to_the_destination(client: TestClient) -> None:
    code = _shorten(client)

    response = client.get(
        f"/{code}?utm_source=sms&utm_campaign=black-friday&ch=qr", follow_redirects=False
    )

    location = response.headers["location"]
    assert "utm_source=sms" in location
    assert "utm_campaign=black-friday" in location
    assert "ch=qr" not in location


def test_a_destination_keeps_its_own_tracking_parameters(client: TestClient) -> None:
    code = client.post(
        "/shorten", json={"url": "https://example.com/offers?utm_source=newsletter"}
    ).json()["code"]

    response = client.get(f"/{code}?utm_source=sms", follow_redirects=False)

    assert "utm_source=newsletter" in response.headers["location"]
    assert "utm_source=sms" not in response.headers["location"]
