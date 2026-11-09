"""Covers the domain rules that do not need storage or HTTP."""

from datetime import UTC, datetime

import pytest

from app.domain import (
    RESERVED_CODES,
    Link,
    average_clicks_per_day,
    classify_device,
    generate_code,
    is_reserved,
    normalise_country,
    weekday_distribution,
)


def test_generated_codes_have_the_requested_length_and_avoid_reserved_words() -> None:
    codes = {generate_code(7) for _ in range(200)}

    assert all(len(code) == 7 for code in codes)
    assert not codes & RESERVED_CODES
    assert len(codes) > 190, "codes should not repeat in a sample this small"


def test_reserved_codes_are_matched_regardless_of_case() -> None:
    assert is_reserved("docs")
    assert is_reserved("DOCS")
    assert not is_reserved("doc")


@pytest.mark.parametrize(
    ("user_agent", "expected"),
    [
        ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)", "mobile"),
        ("Mozilla/5.0 (Linux; Android 14)", "mobile"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "desktop"),
        ("Googlebot/2.1 (+http://www.google.com/bot.html)", "bot"),
        ("curl/8.4.0", "bot"),
        (None, "unknown"),
        ("", "unknown"),
    ],
)
def test_devices_are_classified_into_coarse_categories(
    user_agent: str | None, expected: str
) -> None:
    assert classify_device(user_agent) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ES", "ES"),
        ("es", "ES"),
        (" gb ", "GB"),
        ("XX", None),
        ("T1", None),
        ("ESP", None),
        (None, None),
    ],
)
def test_country_codes_are_validated_rather_than_trusted(
    raw: str | None, expected: str | None
) -> None:
    assert normalise_country(raw) == expected


def test_weekdays_are_folded_from_the_daily_counts() -> None:
    # 2026-11-09 is a Monday, 2026-11-14 a Saturday.
    distribution = weekday_distribution({"2026-11-09": 3, "2026-11-14": 2, "2026-11-16": 1})

    assert distribution["Mon"] == 4
    assert distribution["Sat"] == 2
    assert distribution["Sun"] == 0


def test_the_daily_average_counts_the_day_of_creation() -> None:
    created = datetime(2026, 11, 9, tzinfo=UTC)

    assert average_clicks_per_day(10, created, datetime(2026, 11, 9, tzinfo=UTC)) == 10.0
    assert average_clicks_per_day(10, created, datetime(2026, 11, 13, tzinfo=UTC)) == 2.0


def test_a_link_without_an_expiry_never_expires() -> None:
    link = Link(code="abc", url="https://example.com", label=None, created_at=datetime.now(UTC))

    assert not link.has_expired(datetime(2099, 1, 1, tzinfo=UTC))


def test_a_link_expires_once_its_moment_is_reached() -> None:
    expiry = datetime(2026, 11, 10, tzinfo=UTC)
    link = Link(
        code="abc",
        url="https://example.com",
        label=None,
        created_at=datetime(2026, 11, 9, tzinfo=UTC),
        expires_at=expiry,
    )

    assert not link.has_expired(datetime(2026, 11, 9, 23, 59, tzinfo=UTC))
    assert link.has_expired(expiry)
