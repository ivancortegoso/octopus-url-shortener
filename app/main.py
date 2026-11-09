"""HTTP entry points for the URL shortener."""

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import Settings, get_settings
from app.dependencies import get_storage
from app.domain import Click, Link, generate_code, is_reserved, utc_now
from app.schemas import ShortenRequest, ShortenResponse, StatsResponse
from app.storage import CodeAlreadyExistsError, Storage

# A generated code can collide with one already stored. Retrying a bounded number of
# times keeps the endpoint predictable instead of failing on an unlucky draw.
MAX_CODE_ATTEMPTS = 5

app = FastAPI(
    title="URL shortener",
    description="Shortens URLs and reports basic click analytics.",
    version="0.1.0",
)

StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


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


@app.post("/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten(payload: ShortenRequest, storage: StorageDep, settings: SettingsDep) -> ShortenResponse:
    """Store a URL and return the code that resolves to it."""
    if payload.code is not None:
        link = _store_with_requested_code(
            storage=storage, url=str(payload.url), label=payload.label, code=payload.code
        )
    else:
        link = _store_with_unique_code(
            storage=storage,
            url=str(payload.url),
            label=payload.label,
            code_length=settings.code_length,
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
    for _ in range(MAX_CODE_ATTEMPTS):
        link = Link(code=generate_code(code_length), url=url, label=label, created_at=utc_now())
        try:
            storage.add_link(link)
        except CodeAlreadyExistsError:
            continue
        return link
    raise RuntimeError("Could not generate an unused short code.")


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
