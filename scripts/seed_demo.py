"""Populate a database with a demonstration campaign and a fortnight of clicks.

Four placements of one Black Friday campaign, each with the traffic shape its channel
would really have: a text message lands fast and dies, a poster trickles in by QR all
fortnight. It writes through the same storage the application uses, so nothing here is a
special case.

    uv run python -m scripts.seed_demo
"""

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.domain import CHANNEL_LINK, CHANNEL_QR, Click, Link
from app.storage import SqliteStorage

CAMPAIGN = "black-friday-go"
DESTINATION = "https://octopusenergy.es/tarifas/go"

COUNTRIES = ["ES", "GB", "DE", "FR", "IT", "PT"]
COUNTRY_WEIGHTS = [60, 14, 9, 7, 6, 4]
# Evening hours carry most of a consumer campaign's traffic.
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 7, 9, 8, 7, 8, 9, 8, 7, 8, 11, 16, 20, 22, 18, 12, 6, 3]


@dataclass(frozen=True, slots=True)
class Placement:
    """One channel the campaign was placed in."""

    code: str
    label: str
    channel: str
    daily_range: tuple[int, int]
    # How the placement decays over the fortnight: a text message is read the day it
    # arrives, a printed poster keeps working.
    decay: float
    referrer: str | None


PLACEMENTS = (
    Placement("bf-sms", "Text message to customers", CHANNEL_LINK, (30, 60), 0.72, None),
    Placement("bf-email", "Newsletter", CHANNEL_LINK, (10, 22), 0.85, None),
    Placement(
        "bf-instagram", "Instagram post", CHANNEL_LINK, (8, 20), 0.9, "https://www.instagram.com/"
    ),
    Placement("bf-poster", "Dealership poster", CHANNEL_QR, (3, 9), 1.0, None),
)


def main() -> None:
    random.seed(20261109)
    storage = SqliteStorage(get_settings().database_path)
    created_at = datetime.now(UTC) - timedelta(days=13)
    hours = list(range(24))
    total = 0

    for placement in PLACEMENTS:
        if storage.get_link(placement.code) is None:
            storage.add_link(
                Link(
                    code=placement.code,
                    url=f"{DESTINATION}?placement={placement.code}",
                    label=placement.label,
                    created_at=created_at,
                    campaign=CAMPAIGN,
                )
            )

        low, high = placement.daily_range
        for day in range(14):
            date = created_at + timedelta(days=day)
            volume = round(random.randint(low, high) * placement.decay**day)
            for _ in range(volume):
                moment = date.replace(
                    hour=random.choices(hours, weights=HOUR_WEIGHTS)[0],
                    minute=random.randrange(60),
                    second=random.randrange(60),
                    microsecond=0,
                )
                # Roughly one resolution in twelve is a preview fetch or a link checker.
                automated = random.random() < 0.08
                storage.add_click(
                    Click(
                        code=placement.code,
                        clicked_at=moment,
                        referrer=placement.referrer,
                        country=random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
                        device="bot" if automated else random.choices(
                            ["mobile", "desktop"], weights=[68, 32]
                        )[0],
                        channel=placement.channel,
                        is_bot=automated,
                    )
                )
                total += 1

    stats = storage.get_campaign_statistics(CAMPAIGN)
    assert stats is not None
    print(
        f"Seeded campaign {CAMPAIGN!r} with {len(stats.links)} placements and {total} "
        f"recorded resolutions ({stats.total_clicks} of them people)."
    )
    print(f"Look at /app?code={PLACEMENTS[0].code} or /app?campaign={CAMPAIGN}")


if __name__ == "__main__":
    main()
