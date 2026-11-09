"""Covers the destination rules applied before a link is created."""

import pytest

from app.destinations import UnsafeDestinationError, ensure_safe_destination

SERVICE = "http://localhost:8000"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "https://example.com/deep/path?query=1",
        "https://sub.example.co.uk",
        "https://8.8.8.8/public",
    ],
)
def test_public_destinations_are_accepted(url: str) -> None:
    ensure_safe_destination(url, SERVICE)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/admin",
        "http://127.0.0.1:9000/",
        "http://10.0.0.5/admin",
        "http://192.168.1.1/",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]:8000/",
        "http://printer.local/status",
        "http://service.internal/metrics",
    ],
)
def test_local_and_private_destinations_are_refused(url: str) -> None:
    with pytest.raises(UnsafeDestinationError):
        ensure_safe_destination(url, SERVICE)


def test_a_link_to_the_service_itself_is_refused() -> None:
    with pytest.raises(UnsafeDestinationError):
        ensure_safe_destination("https://short.example/abc123", "https://short.example")
