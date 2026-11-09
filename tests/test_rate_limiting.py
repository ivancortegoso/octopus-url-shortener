"""Covers the sliding-window rate limiter."""

from app.rate_limiting import SlidingWindowRateLimiter, client_key


def test_requests_within_the_allowance_are_permitted() -> None:
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)

    assert [limiter.allow("client", now=1.0) for _ in range(3)] == [True, True, True]


def test_the_request_after_the_allowance_is_refused() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    limiter.allow("client", now=1.0)
    limiter.allow("client", now=1.0)

    assert limiter.allow("client", now=1.0) is False


def test_the_allowance_returns_once_the_window_has_passed() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    limiter.allow("client", now=1.0)

    assert limiter.allow("client", now=30.0) is False
    assert limiter.allow("client", now=62.0) is True


def test_clients_are_counted_separately() -> None:
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    limiter.allow("first", now=1.0)

    assert limiter.allow("second", now=1.0) is True


def test_the_client_key_hides_the_address_and_is_stable() -> None:
    key = client_key("203.0.113.7")

    assert "203.0.113.7" not in key
    assert key == client_key("203.0.113.7")
    assert key != client_key("203.0.113.8")


def test_the_api_answers_429_once_the_allowance_is_spent() -> None:
    from fastapi.testclient import TestClient

    from app.dependencies import get_rate_limiter, get_storage
    from app.main import app
    from app.storage import InMemoryStorage

    # Wrapped in a lambda: handing FastAPI the class would make it read the dataclass
    # fields as request parameters.
    storage = InMemoryStorage()
    app.dependency_overrides[get_storage] = lambda: storage
    # One instance for the whole test: building a new limiter per request would reset
    # the window every time.
    limiter = SlidingWindowRateLimiter(limit=1, window_seconds=60)
    app.dependency_overrides[get_rate_limiter] = lambda: limiter
    try:
        with TestClient(app) as client:
            first = client.post("/shorten", json={"url": "https://example.com"})
            second = client.post("/shorten", json={"url": "https://example.com"})
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 201
    assert second.status_code == 429
    assert "Retry-After" in second.headers
