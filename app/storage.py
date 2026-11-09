"""Persistence for links and clicks.

The brief offered either SQLite or in-memory Python structures. Both are here behind one
protocol: SQLite backs the running service, because click analytics that vanish on
restart answer nothing, and the in-memory implementation keeps the tests free of files.

The schema is created on first use. There is no migration tooling, so a database file
written by an earlier version of this code is not upgraded; that is the first thing a
real deployment would need.
"""

import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain import Click, Link

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code       TEXT PRIMARY KEY,
    url        TEXT NOT NULL,
    label      TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL REFERENCES links(code),
    clicked_at TEXT NOT NULL,
    referrer   TEXT,
    country    TEXT,
    device     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS clicks_by_code ON clicks(code);
"""

TOP_REFERRER_LIMIT = 5


@dataclass(frozen=True, slots=True)
class LinkStatistics:
    """What the service knows about one short code.

    Only what storage can answer. The daily average and the weekday distribution are
    derived from these figures in the domain, so the two implementations cannot disagree.
    """

    link: Link
    total_clicks: int
    first_clicked_at: datetime | None
    last_clicked_at: datetime | None
    clicks_per_day: dict[str, int]
    clicks_by_hour: dict[str, int]
    clicks_by_country: dict[str, int]
    clicks_by_device: dict[str, int]
    top_referrers: dict[str, int]


class CodeAlreadyExistsError(Exception):
    """Raised when a code is already taken."""


class Storage(Protocol):
    """The persistence operations the application needs."""

    def add_link(self, link: Link) -> None: ...

    def get_link(self, code: str) -> Link | None: ...

    def add_click(self, click: Click) -> None: ...

    def get_statistics(self, code: str) -> LinkStatistics | None: ...


class SqliteStorage:
    """Stores links and clicks in a SQLite file."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        with self._connect() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Open a connection for a single operation.

        A connection per operation keeps the storage usable from the worker threads
        FastAPI runs synchronous endpoints on, where sharing one connection is unsafe.
        Opening a SQLite connection is a file handle, not a network handshake.
        """
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            # Write-ahead logging lets reads continue while a write is in progress, which
            # suits a service whose redirects vastly outnumber its creations.
            connection.execute("PRAGMA journal_mode=WAL")
            # SQLite ignores declared foreign keys unless asked, on every connection.
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add_link(self, link: Link) -> None:
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO links (code, url, label, created_at, expires_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        link.code,
                        link.url,
                        link.label,
                        link.created_at.isoformat(),
                        link.expires_at.isoformat() if link.expires_at else None,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise CodeAlreadyExistsError(link.code) from error

    def get_link(self, code: str) -> Link | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT code, url, label, created_at, expires_at FROM links WHERE code = ?",
                (code,),
            ).fetchone()
        return _row_to_link(row) if row else None

    def add_click(self, click: Click) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO clicks (code, clicked_at, referrer, country, device)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    click.code,
                    click.clicked_at.isoformat(),
                    click.referrer,
                    click.country,
                    click.device,
                ),
            )

    def get_statistics(self, code: str) -> LinkStatistics | None:
        with self._connect() as connection:
            link_row = connection.execute(
                "SELECT code, url, label, created_at, expires_at FROM links WHERE code = ?",
                (code,),
            ).fetchone()
            if link_row is None:
                return None

            totals = connection.execute(
                "SELECT COUNT(*) AS total, MIN(clicked_at) AS first, MAX(clicked_at) AS last"
                " FROM clicks WHERE code = ?",
                (code,),
            ).fetchone()
            # Timestamps are stored as ISO 8601, which sorts alphabetically in the same
            # order it sorts chronologically, so slicing the fixed-width prefix groups by
            # date and the one after it by hour. Both are UTC.
            per_day = connection.execute(
                "SELECT substr(clicked_at, 1, 10) AS bucket, COUNT(*) AS hits"
                " FROM clicks WHERE code = ? GROUP BY bucket ORDER BY bucket",
                (code,),
            ).fetchall()
            per_hour = connection.execute(
                "SELECT substr(clicked_at, 12, 2) AS bucket, COUNT(*) AS hits"
                " FROM clicks WHERE code = ? GROUP BY bucket ORDER BY bucket",
                (code,),
            ).fetchall()
            per_country = connection.execute(
                "SELECT country AS bucket, COUNT(*) AS hits FROM clicks"
                " WHERE code = ? AND country IS NOT NULL"
                " GROUP BY bucket ORDER BY hits DESC, bucket",
                (code,),
            ).fetchall()
            per_device = connection.execute(
                "SELECT device AS bucket, COUNT(*) AS hits FROM clicks"
                " WHERE code = ? GROUP BY bucket ORDER BY hits DESC, bucket",
                (code,),
            ).fetchall()
            referrers = connection.execute(
                "SELECT referrer AS bucket, COUNT(*) AS hits FROM clicks"
                " WHERE code = ? AND referrer IS NOT NULL"
                " GROUP BY bucket ORDER BY hits DESC, bucket LIMIT ?",
                (code, TOP_REFERRER_LIMIT),
            ).fetchall()

        return LinkStatistics(
            link=_row_to_link(link_row),
            total_clicks=totals["total"],
            first_clicked_at=_parse_optional(totals["first"]),
            last_clicked_at=_parse_optional(totals["last"]),
            clicks_per_day=_buckets(per_day),
            clicks_by_hour=_buckets(per_hour),
            clicks_by_country=_buckets(per_country),
            clicks_by_device=_buckets(per_device),
            top_referrers=_buckets(referrers),
        )


@dataclass
class InMemoryStorage:
    """Stores links and clicks in dictionaries, for tests and throwaway runs."""

    links: dict[str, Link] = field(default_factory=dict)
    clicks: list[Click] = field(default_factory=list)

    def add_link(self, link: Link) -> None:
        if link.code in self.links:
            raise CodeAlreadyExistsError(link.code)
        self.links[link.code] = link

    def get_link(self, code: str) -> Link | None:
        return self.links.get(code)

    def add_click(self, click: Click) -> None:
        self.clicks.append(click)

    def get_statistics(self, code: str) -> LinkStatistics | None:
        link = self.links.get(code)
        if link is None:
            return None

        clicks = [click for click in self.clicks if click.code == code]
        moments = [click.clicked_at for click in clicks]

        return LinkStatistics(
            link=link,
            total_clicks=len(clicks),
            first_clicked_at=min(moments, default=None),
            last_clicked_at=max(moments, default=None),
            clicks_per_day=_ordered(
                Counter(click.clicked_at.date().isoformat() for click in clicks)
            ),
            clicks_by_hour=_ordered(
                Counter(f"{click.clicked_at.hour:02d}" for click in clicks)
            ),
            clicks_by_country=_ranked(
                Counter(click.country for click in clicks if click.country)
            ),
            clicks_by_device=_ranked(Counter(click.device for click in clicks)),
            top_referrers=_ranked(
                Counter(click.referrer for click in clicks if click.referrer),
                limit=TOP_REFERRER_LIMIT,
            ),
        )


def _row_to_link(row: sqlite3.Row) -> Link:
    return Link(
        code=row["code"],
        url=row["url"],
        label=row["label"],
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=_parse_optional(row["expires_at"]),
    )


def _parse_optional(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _buckets(rows: list[sqlite3.Row]) -> dict[str, int]:
    return {str(row["bucket"]): int(row["hits"]) for row in rows}


def _ordered(counts: Counter[str]) -> dict[str, int]:
    return dict(sorted(counts.items()))


def _ranked(counts: Counter[str], limit: int | None = None) -> dict[str, int]:
    """Order by count descending, then by name, matching the SQL implementation."""
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return dict(ranked[:limit] if limit else ranked)
