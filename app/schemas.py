"""Request and response bodies for the HTTP API."""

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Readable aliases are the point of the custom-code feature, so the character set stays to
# what reads well in print or read aloud and survives being copied out of an email.
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
    expires_at: datetime | None = Field(
        default=None,
        description="When the link stops resolving. A timestamp without a zone is read as UTC.",
    )

    @field_validator("expires_at")
    @classmethod
    def _reject_past_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        if moment <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future.")
        return moment


class ShortenResponse(BaseModel):
    """The body returned by POST /shorten."""

    code: str
    short_url: str
    expires_at: datetime | None = None


class StatsResponse(BaseModel):
    """The body returned by GET /stats/{code}.

    Every distribution is keyed in UTC. A service spanning several time zones would need
    to carry the zone the reader cares about; for now the convention is stated rather than
    guessed at.
    """

    code: str
    url: str
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    is_expired: bool
    total_clicks: int
    first_clicked_at: datetime | None
    last_clicked_at: datetime | None
    average_clicks_per_day: float
    clicks_per_day: dict[str, int]
    clicks_by_hour: dict[str, int]
    clicks_by_weekday: dict[str, int]
    clicks_by_country: dict[str, int]
    clicks_by_device: dict[str, int]
    top_referrers: dict[str, int]
