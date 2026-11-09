"""The vocabulary of the service: what a link is, what a click is, how codes are made."""

import secrets
import string
from dataclasses import dataclass
from datetime import UTC, datetime

CODE_ALPHABET = string.ascii_letters + string.digits

# Paths the application serves itself. A generated code that matched one of these would
# produce a link that can never resolve, so they are excluded from the alphabet soup.
RESERVED_CODES = frozenset({"docs", "redoc", "openapi.json", "stats", "shorten"})


@dataclass(frozen=True, slots=True)
class Link:
    """A shortened URL and the code that resolves to it."""

    code: str
    url: str
    label: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class Click:
    """A single resolution of a short code.

    No IP address is recorded: it is personal data under the GDPR and none of the
    questions this service answers need it.
    """

    code: str
    clicked_at: datetime
    referrer: str | None
    user_agent: str | None


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


def utc_now() -> datetime:
    return datetime.now(UTC)


def is_reserved(code: str) -> bool:
    """Report whether a code names a path the service serves itself."""
    return code.lower() in RESERVED_CODES
