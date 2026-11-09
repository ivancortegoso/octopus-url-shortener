"""HTTP entry points for the URL shortener."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings, get_settings
from app.dependencies import get_rate_limiter, get_storage
from app.destinations import UnsafeDestinationError, ensure_safe_destination
from app.domain import Click, Link, generate_code, is_reserved, utc_now
from app.rate_limiting import SlidingWindowRateLimiter, client_key
from app.schemas import ShortenRequest, ShortenResponse, StatsResponse
from app.storage import CodeAlreadyExistsError, Storage

# A generated code can collide with one already stored. Retrying a bounded number of
# times keeps the endpoint predictable instead of failing on an unlucky draw.
MAX_CODE_ATTEMPTS = 5

_settings = get_settings()

app = FastAPI(
    title="URL shortener",
    description="Shortens URLs and reports basic click analytics.",
    version="0.1.0",
    docs_url="/docs" if _settings.docs_enabled else None,
    redoc_url="/redoc" if _settings.docs_enabled else None,
    openapi_url="/openapi.json" if _settings.docs_enabled else None,
)

StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
RateLimiterDep = Annotated[SlidingWindowRateLimiter, Depends(get_rate_limiter)]


def enforce_rate_limit(request: Request, limiter: RateLimiterDep) -> None:
    """Refuse the request when this client has exhausted its allowance."""
    address = request.client.host if request.client else "unknown"
    if not limiter.allow(client_key(address)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many links created from this address. Try again shortly.",
            headers={"Retry-After": str(get_settings().rate_limit_window_seconds)},
        )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    """Answer malformed bodies with 400.

    FastAPI returns 422 for validation failures. The brief specifies 400 for an invalid
    URL, so the status is remapped here rather than validating by hand in the route.
    """
    details = [
        {
            "field": ".".join(str(part) for part in item["loc"][1:]),
            "message": item["msg"],
        }
        for item in error.errors()
    ]
    return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"detail": details})


@app.post(
    "/shorten",
    response_model=ShortenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_rate_limit)],
    summary="Create a short link",
)
def shorten(payload: ShortenRequest, storage: StorageDep, settings: SettingsDep) -> ShortenResponse:
    """Store a URL and return the code that resolves to it."""
    url = str(payload.url)
    try:
        ensure_safe_destination(url, settings.base_url)
    except UnsafeDestinationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
        ) from error

    if payload.code is not None:
        link = _store_with_requested_code(
            storage=storage, url=url, label=payload.label, code=payload.code
        )
    else:
        link = _store_with_unique_code(
            storage=storage, url=url, label=payload.label, code_length=settings.code_length
        )
    return ShortenResponse(code=link.code, short_url=f"{settings.base_url}/{link.code}")


def _store_with_requested_code(
    *, storage: Storage, url: str, label: str | None, code: str
) -> Link:
    """Store a link under a caller-chosen code, refusing one that is taken or reserved."""
    if is_reserved(code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The code {code!r} is reserved by the service.",
        )

    link = Link(code=code, url=url, label=label, created_at=utc_now())
    try:
        storage.add_link(link)
    except CodeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The code {code!r} is already taken.",
        ) from error
    return link


def _store_with_unique_code(
    *, storage: Storage, url: str, label: str | None, code_length: int
) -> Link:
    """Store a link under a generated code, retrying a bounded number of collisions."""
    for _ in range(MAX_CODE_ATTEMPTS):
        link = Link(code=generate_code(code_length), url=url, label=label, created_at=utc_now())
        try:
            storage.add_link(link)
        except CodeAlreadyExistsError:
            continue
        return link

    # Reaching here means the code space is saturated at the configured length, which is a
    # capacity problem rather than a fault in the request.
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Could not allocate an unused short code. Try again or raise CODE_LENGTH.",
    )


@app.get(
    "/stats/{code}",
    response_model=StatsResponse,
    summary="Report what is known about a short code",
)
def statistics(code: str, storage: StorageDep) -> StatsResponse:
    """Return the original URL and the click analytics recorded for it."""
    stats = storage.get_statistics(code)
    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown short code.")

    return StatsResponse(
        code=stats.link.code,
        url=stats.link.url,
        label=stats.link.label,
        created_at=stats.link.created_at,
        total_clicks=stats.total_clicks,
        last_clicked_at=stats.last_clicked_at,
        clicks_per_day=stats.clicks_per_day,
        top_referrers=stats.top_referrers,
    )


# Declared last: this pattern matches any single path segment, so every fixed route the
# service exposes has to be registered before it.
@app.get(
    "/{code}",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Resolve a short code",
)
def follow(code: str, request: Request, storage: StorageDep) -> RedirectResponse:
    """Redirect to the original URL and record the click."""
    link = storage.get_link(code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown short code.")

    storage.add_click(
        Click(
            code=code,
            clicked_at=utc_now(),
            # The HTTP header has carried the historical misspelling "referer" since 1996.
            referrer=request.headers.get("referer"),
            user_agent=request.headers.get("user-agent"),
        )
    )
    return RedirectResponse(url=link.url, status_code=status.HTTP_302_FOUND)
