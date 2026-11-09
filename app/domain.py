"""The vocabulary of the service: what a link is, what a click is, how codes are made."""

import secrets
import string
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

CODE_ALPHABET = string.ascii_letters + string.digits

# Paths the application serves itself. A generated code that matched one of these would
# produce a link that can never resolve, so they are excluded.
RESERVED_CODES = frozenset(
    {"docs", "redoc", "openapi.json", "stats", "shorten", "qr", "app", "health", "ready"}
)

# User agents name themselves, and they imitate each other, so these are indicative.
# The chat clients matter in practice: pasting a short link into a conversation makes the
# platform fetch it to build a preview, and that fetch is not a person.
BOT_TOKENS = (
    "bot",
    "crawler",
    "spider",
    "curl",
    "wget",
    "python-requests",
    "httpx",
    "slackbot",
    "whatsapp",
    "facebookexternalhit",
    "telegrambot",
    "discordbot",
    "linkedinbot",
    "embedly",
    "preview",
)
MOBILE_TOKENS = ("android", "iphone", "ipad", "ipod", "mobile", "windows phone")

WEEKDAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")

# How a visitor reached the link. A scanned code and a tapped link answer different
# questions for whoever placed them.
CHANNEL_LINK = "link"
CHANNEL_QR = "qr"
CHANNEL_PARAMETER = "ch"

# Campaign parameters a caller may put on the short link; they are carried through to the
# destination so the analytics on the far side agree with ours.
TRACKING_PREFIX = "utm_"


@dataclass(frozen=True, slots=True)
class Link:
    """A shortened URL and the code that resolves to it."""

    code: str
    url: str
    label: str | None
    created_at: datetime
    expires_at: datetime | None = None
    fallback_url: str | None = None
    campaign: str | None = None

    def has_expired(self, moment: datetime) -> bool:
        return self.expires_at is not None and moment >= self.expires_at

    def destination(self, moment: datetime) -> str | None:
        """Return where a visitor should be sent now, or None when the link is gone.

        An expired link with a fallback still has somewhere useful to send people: a
        campaign page that has ended is better answered with the tariff listing than with
        an error, particularly when the link is printed on something still circulating.
        """
        if not self.has_expired(moment):
            return self.url
        return self.fallback_url


@dataclass(frozen=True, slots=True)
class Click:
    """A single resolution of a short code.

    Deliberately narrow. No IP address is stored: it is personal data in every
    jurisdiction this could run in, and none of the questions the statistics answer need
    one. The country is resolved at the network edge and arrives as a two-letter code,
    which on its own singles out nobody. The user agent is reduced to a device category
    for the same reason: the full string is a fingerprinting vector.
    """

    code: str
    clicked_at: datetime
    referrer: str | None
    country: str | None
    device: str
    channel: str = CHANNEL_LINK
    is_bot: bool = False
    after_expiry: bool = False


def generate_code(length: int) -> str:
    """Return a random code drawn from a 62-character alphabet.

    Randomness rather than a counter or a hash of the URL: a counter leaks how many links
    exist and invites enumeration, and hashing means the same URL always yields the same
    code, which removes the option of shortening one URL twice on purpose.
    """
    while True:
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
        if code not in RESERVED_CODES:
            return code


def is_reserved(code: str) -> bool:
    """Report whether a code names a path the service serves itself."""
    return code.lower() in RESERVED_CODES


def classify_device(user_agent: str | None) -> str:
    """Reduce a user agent to one of bot, mobile, desktop or unknown."""
    if not user_agent:
        return "unknown"

    agent = user_agent.lower()
    if any(token in agent for token in BOT_TOKENS):
        return "bot"
    if any(token in agent for token in MOBILE_TOKENS):
        return "mobile"
    return "desktop"


def normalise_country(raw: str | None) -> str | None:
    """Accept a two-letter country code from the edge, rejecting anything else.

    Content delivery networks send placeholders such as "XX" when they cannot place a
    request and "T1" for traffic arriving over Tor, so the shape is checked rather than
    trusted.
    """
    if raw is None:
        return None

    code = raw.strip().upper()
    if len(code) != 2 or not code.isalpha() or code == "XX":
        return None
    return code


def weekday_distribution(clicks_per_day: dict[str, int]) -> dict[str, int]:
    """Fold a per-date count into a Monday-to-Sunday distribution.

    Derived from the daily counts rather than queried separately: every date belongs to
    exactly one weekday, so the two cannot disagree, and the storage implementations do
    not each need their own version of the calendar.
    """
    distribution = dict.fromkeys(WEEKDAY_NAMES, 0)
    for day, hits in clicks_per_day.items():
        distribution[WEEKDAY_NAMES[datetime.fromisoformat(day).weekday()]] += hits
    return distribution


def average_clicks_per_day(total_clicks: int, created_at: datetime, until: datetime) -> float:
    """Return the mean clicks per day a link has seen since it was created."""
    days = max((until.date() - created_at.date()).days + 1, 1)
    return round(total_clicks / days, 2)


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_automated(method: str, device: str) -> bool:
    """Report whether a resolution came from a program rather than a person.

    Two signals, both cheap. A HEAD request asks where a link goes without opening it,
    which is what link checkers and preview services do. And the user agent may name
    itself as a robot.
    """
    return method.upper() == "HEAD" or device == "bot"


def channel_from(parameter: str | None) -> str:
    """Read the channel a visitor arrived through, defaulting to a tapped link."""
    return CHANNEL_QR if parameter == CHANNEL_QR else CHANNEL_LINK


def forward_tracking_parameters(destination: str, incoming: dict[str, str]) -> str:
    """Carry utm_* parameters from the short link through to the destination.

    Whoever placed the link may tag it, and the page on the far side has its own analytics
    that read those tags. Parameters already on the destination win, because the person
    who wrote the destination was more specific than the person who tagged the link.
    """
    tracking = {
        key: value for key, value in incoming.items() if key.startswith(TRACKING_PREFIX)
    }
    if not tracking:
        return destination

    parts = urlsplit(destination)
    merged = dict(parse_qsl(parts.query, keep_blank_values=True))
    for key, value in tracking.items():
        merged.setdefault(key, value)
    return urlunsplit(parts._replace(query=urlencode(merged)))
