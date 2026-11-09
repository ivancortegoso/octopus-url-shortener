"""HTTP entry points for the URL shortener."""

from typing import Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.dependencies import get_storage
from app.domain import Link, generate_code, utc_now
from app.schemas import ShortenRequest, ShortenResponse
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
    link = _store_with_unique_code(
        storage=storage,
        url=str(payload.url),
        label=payload.label,
        code_length=settings.code_length,
    )
    return ShortenResponse(code=link.code, short_url=f"{settings.base_url}/{link.code}")


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
