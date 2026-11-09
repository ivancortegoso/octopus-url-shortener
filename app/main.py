"""HTTP entry points for the URL shortener."""

import io
from datetime import datetime
from pathlib import Path
from typing import Annotated

import segno
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from app.config import Settings, get_settings
from app.dependencies import get_rate_limiter, get_storage
from app.destinations import UnsafeDestinationError, ensure_safe_destination
from app.domain import (
    CHANNEL_PARAMETER,
    CHANNEL_QR,
    Click,
    Link,
    average_clicks_per_day,
    channel_from,
    classify_device,
    forward_tracking_parameters,
    generate_code,
    is_automated,
    is_reserved,
    normalise_country,
    utc_now,
    weekday_distribution,
)
from app.observability import configure_logging, log_request
from app.rate_limiting import SlidingWindowRateLimiter, client_key
from app.schemas import (
    CampaignLink,
    CampaignStatsResponse,
    ShortenRequest,
    ShortenResponse,
    StatsResponse,
)
from app.storage import CodeAlreadyExistsError, Storage

# A generated code can collide with one already stored. Retrying a bounded number of
# times keeps the endpoint predictable instead of failing on an unlucky draw.
MAX_CODE_ATTEMPTS = 5

# Content delivery networks resolve the visitor's country at the edge and pass it on, so
# the application never sees an IP address.
COUNTRY_HEADERS = ("cf-ipcountry", "x-vercel-ip-country", "x-country-code")

QR_SCALE = 6
STATIC_DIR = Path(__file__).parent / "static"

_settings = get_settings()
configure_logging()

app = FastAPI(
    title="URL shortener",
    description="Shortens URLs and reports basic click analytics.",
    version="0.1.0",
    docs_url="/docs" if _settings.docs_enabled else None,
    redoc_url="/redoc" if _settings.docs_enabled else None,
    openapi_url="/openapi.json" if _settings.docs_enabled else None,
)

app.middleware("http")(log_request)

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


@app.get("/health", summary="Report that the service is running")
def health() -> dict[str, str]:
    """Answer the liveness check a platform uses to decide whether to restart."""
    return {"status": "ok"}


@app.get("/app", response_class=FileResponse, include_in_schema=False)
def dashboard() -> FileResponse:
    """Serve the single page that reads the public statistics API."""
    return FileResponse(STATIC_DIR / "index.html")


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
    fallback_url = str(payload.fallback_url) if payload.fallback_url else None
    for candidate in (url, fallback_url):
        if candidate is None:
            continue
        try:
            ensure_safe_destination(candidate, settings.base_url)
        except UnsafeDestinationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)
            ) from error

    if payload.code is not None:
        link = _store_with_requested_code(
            storage=storage,
            url=url,
            label=payload.label,
            code=payload.code,
            expires_at=payload.expires_at,
            fallback_url=fallback_url,
            campaign=payload.campaign,
        )
    else:
        link = _store_with_unique_code(
            storage=storage,
            url=url,
            label=payload.label,
            code_length=settings.code_length,
            expires_at=payload.expires_at,
            fallback_url=fallback_url,
            campaign=payload.campaign,
        )

    return ShortenResponse(
        code=link.code,
        short_url=f"{settings.base_url}/{link.code}",
        expires_at=link.expires_at,
        fallback_url=link.fallback_url,
        campaign=link.campaign,
    )


def _store_with_requested_code(
    *,
    storage: Storage,
    url: str,
    label: str | None,
    code: str,
    expires_at: datetime | None,
    fallback_url: str | None,
    campaign: str | None,
) -> Link:
    """Store a link under a caller-chosen code, refusing one that is taken or reserved."""
    if is_reserved(code):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The code {code!r} is reserved by the service.",
        )

    link = Link(
        code=code,
        url=url,
        label=label,
        created_at=utc_now(),
        expires_at=expires_at,
        fallback_url=fallback_url,
        campaign=campaign,
    )
    try:
        storage.add_link(link)
    except CodeAlreadyExistsError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The code {code!r} is already taken.",
        ) from error
    return link


def _store_with_unique_code(
    *,
    storage: Storage,
    url: str,
    label: str | None,
    code_length: int,
    expires_at: datetime | None,
    fallback_url: str | None,
    campaign: str | None,
) -> Link:
    """Store a link under a generated code, retrying a bounded number of collisions."""
    for _ in range(MAX_CODE_ATTEMPTS):
        link = Link(
            code=generate_code(code_length),
            url=url,
            label=label,
            created_at=utc_now(),
            expires_at=expires_at,
            fallback_url=fallback_url,
            campaign=campaign,
        )
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

    now = utc_now()
    return StatsResponse(
        code=stats.link.code,
        url=stats.link.url,
        label=stats.link.label,
        campaign=stats.link.campaign,
        created_at=stats.link.created_at,
        expires_at=stats.link.expires_at,
        is_expired=stats.link.has_expired(now),
        fallback_url=stats.link.fallback_url,
        total_clicks=stats.total_clicks,
        bot_clicks=stats.bot_clicks,
        expired_clicks=stats.expired_clicks,
        first_clicked_at=stats.first_clicked_at,
        last_clicked_at=stats.last_clicked_at,
        average_clicks_per_day=average_clicks_per_day(
            stats.total_clicks, stats.link.created_at, now
        ),
        clicks_per_day=stats.clicks_per_day,
        clicks_by_hour=stats.clicks_by_hour,
        clicks_by_weekday=weekday_distribution(stats.clicks_per_day),
        clicks_by_country=stats.clicks_by_country,
        clicks_by_device=stats.clicks_by_device,
        clicks_by_channel=stats.clicks_by_channel,
        top_referrers=stats.top_referrers,
    )


@app.get(
    "/stats/campaign/{campaign}",
    response_model=CampaignStatsResponse,
    summary="Report every link placed for one campaign",
)
def campaign_statistics(campaign: str, storage: StorageDep) -> CampaignStatsResponse:
    """Return the campaign's links ranked by the traffic each one brought."""
    stats = storage.get_campaign_statistics(campaign)
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No links carry that campaign."
        )

    return CampaignStatsResponse(
        campaign=stats.campaign,
        total_clicks=stats.total_clicks,
        bot_clicks=stats.bot_clicks,
        links=[
            CampaignLink(
                code=summary.code,
                url=summary.url,
                label=summary.label,
                total_clicks=summary.total_clicks,
            )
            for summary in stats.links
        ],
        clicks_by_channel=stats.clicks_by_channel,
        clicks_by_country=stats.clicks_by_country,
        clicks_by_device=stats.clicks_by_device,
    )


@app.get("/qr/{code}", response_class=Response, summary="Render a short link as a QR code")
def qr_code(code: str, storage: StorageDep, settings: SettingsDep) -> Response:
    """Return the short URL as a PNG QR code, for print and screens."""
    if storage.get_link(code) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown short code.")

    image = io.BytesIO()
    # The encoded link carries the channel, so a scan is distinguishable from a tap.
    target = f"{settings.base_url}/{code}?{CHANNEL_PARAMETER}={CHANNEL_QR}"
    segno.make(target, error="m").save(image, kind="png", scale=QR_SCALE)
    return Response(
        content=image.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"},
    )


# Declared last: this pattern matches any single path segment, so every fixed route the
# service exposes has to be registered before it.
@app.api_route(
    "/{code}",
    # HEAD as well as GET: link checkers and the brief's own `curl -I` example ask where a
    # code leads without opening it, and answering 405 to them would be wrong.
    methods=["GET", "HEAD"],
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    summary="Resolve a short code",
)
def follow(code: str, request: Request, storage: StorageDep) -> RedirectResponse:
    """Redirect to the original URL and record the click."""
    link = storage.get_link(code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown short code.")

    now = utc_now()
    expired = link.has_expired(now)
    device = classify_device(request.headers.get("user-agent"))

    storage.add_click(
        Click(
            code=code,
            clicked_at=now,
            # The HTTP header has carried the historical misspelling "referer" since 1996.
            referrer=request.headers.get("referer"),
            country=_country_from_edge(request),
            device=device,
            channel=channel_from(request.query_params.get(CHANNEL_PARAMETER)),
            is_bot=is_automated(request.method, device),
            after_expiry=expired,
        )
    )

    destination = link.destination(now)
    if destination is None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="This link has expired.")

    return RedirectResponse(
        url=forward_tracking_parameters(destination, dict(request.query_params)),
        status_code=status.HTTP_302_FOUND,
    )


def _country_from_edge(request: Request) -> str | None:
    """Read the country the edge resolved, if any proxy in front supplied one."""
    for header in COUNTRY_HEADERS:
        country = normalise_country(request.headers.get(header))
        if country is not None:
            return country
    return None
