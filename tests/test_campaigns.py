"""Covers reading every link placed for one campaign."""

from fastapi.testclient import TestClient

CAMPAIGN = "black-friday-go"


def _place(client: TestClient, code: str, label: str) -> None:
    client.post(
        "/shorten",
        json={
            "url": f"https://example.com/offers?placement={code}",
            "code": code,
            "label": label,
            "campaign": CAMPAIGN,
        },
    )


def test_a_campaign_reports_each_placement_ranked_by_traffic(client: TestClient) -> None:
    _place(client, "bf-sms", "SMS to customers")
    _place(client, "bf-email", "Newsletter")
    for _ in range(3):
        client.get("/bf-sms", follow_redirects=False)
    client.get("/bf-email", follow_redirects=False)

    body = client.get(f"/stats/campaign/{CAMPAIGN}").json()

    assert body["total_clicks"] == 4
    assert [link["code"] for link in body["links"]] == ["bf-sms", "bf-email"]
    assert body["links"][0]["total_clicks"] == 3
    assert body["links"][0]["label"] == "SMS to customers"


def test_a_campaign_separates_scans_from_taps(client: TestClient) -> None:
    _place(client, "bf-poster", "Dealership poster")
    client.get("/bf-poster?ch=qr", follow_redirects=False)
    client.get("/bf-poster", follow_redirects=False)

    body = client.get(f"/stats/campaign/{CAMPAIGN}").json()

    assert body["clicks_by_channel"] == {"link": 1, "qr": 1}


def test_a_campaign_excludes_automated_traffic_from_its_total(client: TestClient) -> None:
    _place(client, "bf-sms", "SMS to customers")
    client.get("/bf-sms", follow_redirects=False, headers={"user-agent": "Slackbot 1.0"})
    client.get("/bf-sms", follow_redirects=False)

    body = client.get(f"/stats/campaign/{CAMPAIGN}").json()

    assert body["total_clicks"] == 1
    assert body["bot_clicks"] == 1


def test_a_link_with_no_clicks_still_appears_in_its_campaign(client: TestClient) -> None:
    _place(client, "bf-unused", "Never shared")

    body = client.get(f"/stats/campaign/{CAMPAIGN}").json()

    assert body["links"] == [
        {
            "code": "bf-unused",
            "url": "https://example.com/offers?placement=bf-unused",
            "label": "Never shared",
            "total_clicks": 0,
        }
    ]


def test_an_unknown_campaign_returns_404(client: TestClient) -> None:
    assert client.get("/stats/campaign/nothing-like-this").status_code == 404
