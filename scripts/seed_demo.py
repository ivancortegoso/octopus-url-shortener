"""Populate a database with a demonstration link and a fortnight of clicks.

For showing the service with something to look at. It writes through the same storage the
application uses, so nothing here is a special case.

    uv run python -m scripts.seed_demo
"""

import random
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.domain import Click, Link
from app.storage import SqliteStorage

DEMO_CODE = "black-friday"
DEMO_URL = "https://octopusenergy.es/tarifas"
COUNTRIES = ["ES", "GB", "DE", "FR", "IT", "PT"]
COUNTRY_WEIGHTS = [50, 20, 10, 8, 7, 5]
DEVICES = ["mobile", "desktop", "bot"]
DEVICE_WEIGHTS = [62, 33, 5]
REFERRERS = [
    "https://www.instagram.com/",
    "https://news.ycombinator.com/",
    "https://www.google.com/",
    None,
]
REFERRER_WEIGHTS = [40, 15, 30, 15]
# Evening hours carry most of the traffic, which is what a consumer campaign looks like.
HOUR_WEIGHTS = [1, 1, 1, 1, 1, 2, 4, 7, 9, 8, 7, 8, 9, 8, 7, 8, 11, 16, 20, 22, 18, 12, 6, 3]


def main() -> None:
    random.seed(20261109)
    storage = SqliteStorage(get_settings().database_path)
    created_at = datetime.now(UTC) - timedelta(days=13)

    if storage.get_link(DEMO_CODE) is None:
        storage.add_link(
            Link(
                code=DEMO_CODE,
                url=DEMO_URL,
                label="Black Friday tariff campaign",
                created_at=created_at,
                expires_at=None,
            )
        )

    hours = list(range(24))
    for day in range(14):
        date = created_at + timedelta(days=day)
        # A campaign ramps up and tails off rather than drawing a flat line.
        for _ in range(random.randint(8, 34)):
            moment = date.replace(
                hour=random.choices(hours, weights=HOUR_WEIGHTS)[0],
                minute=random.randrange(60),
                second=random.randrange(60),
                microsecond=0,
            )
            storage.add_click(
                Click(
                    code=DEMO_CODE,
                    clicked_at=moment,
                    referrer=random.choices(REFERRERS, weights=REFERRER_WEIGHTS)[0],
                    country=random.choices(COUNTRIES, weights=COUNTRY_WEIGHTS)[0],
                    device=random.choices(DEVICES, weights=DEVICE_WEIGHTS)[0],
                )
            )

    stats = storage.get_statistics(DEMO_CODE)
    assert stats is not None
    print(f"Seeded /{DEMO_CODE} with {stats.total_clicks} clicks across 14 days.")


if __name__ == "__main__":
    main()
