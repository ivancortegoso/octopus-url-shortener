"""Request and response bodies for the HTTP API."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl

# Readable aliases are the point of the feature, so the character set stays to what reads
# well in a printed or spoken link and survives being copied out of an email.
CUSTOM_CODE_PATTERN = r"^[A-Za-z0-9_-]{3,32}$"


class ShortenRequest(BaseModel):
    """The body accepted by POST /shorten."""

    url: HttpUrl = Field(description="The http or https URL to shorten.")
    label: str | None = Field(
        default=None, max_length=200, description="An optional human-readable name."
    )
    code: str | None = Field(
        default=None,
        pattern=CUSTOM_CODE_PATTERN,
        description=(
            "An optional code to use instead of a generated one. Letters, digits, hyphens "
            "and underscores, 3 to 32 characters."
        ),
    )


class ShortenResponse(BaseModel):
    """The body returned by POST /shorten."""

    code: str
    short_url: str


class StatsResponse(BaseModel):
    """The body returned by GET /stats/{code}."""

    code: str
    url: str
    label: str | None
    created_at: datetime
    total_clicks: int
    last_clicked_at: datetime | None
    clicks_per_day: dict[str, int]
    top_referrers: dict[str, int]
