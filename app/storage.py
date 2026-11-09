"""Persistence for links and clicks.

The brief offered either SQLite or in-memory Python structures. Both are here behind one
protocol: SQLite backs the running service, because click analytics that vanish on
restart answer nothing, and the in-memory implementation keeps the tests free of files.

The schema is created on first use. There is no migration tooling, so a database file
written by an earlier version of this code is not upgraded; that is the first thing a real
deployment would need.
"""

import sqlite3
from collections import Counter
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.domain import Click, Link

SCHEMA = """
CREATE TABLE IF NOT EXISTS links (
    code         TEXT PRIMARY KEY,
    url          TEXT NOT NULL,
    label        TEXT,
    created_at   TEXT NOT NULL,
    expires_at   TEXT,
    fallback_url TEXT,
    campaign     TEXT
);

CREATE TABLE IF NOT EXISTS clicks (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    code         TEXT NOT NULL REFERENCES links(code),
    clicked_at   TEXT NOT NULL,
    referrer     TEXT,
    country      TEXT,
    device       TEXT NOT NULL,
    channel      TEXT NOT NULL,
    is_bot       INTEGER NOT NULL DEFAULT 0,
    after_expiry INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS clicks_by_code ON clicks(code);
CREATE INDEX IF NOT EXISTS links_by_campaign ON links(campaign);
"""

TOP_REFERRER_LIMIT = 5

# Every distribution describes people, so automated resolutions and the ones that arrived
# after a link expired are counted separately rather than mixed in.
HUMAN_CLICK = "is_bot = 0 AND after_expiry = 0"


@dataclass(frozen=True, slots=True)
class LinkStatistics:
    """What the service knows about one short code.

    Only what storage can answer. The daily average and the weekday distribution are
    derived from these figures in the domain, so the two implementations cannot disagree.
    """

    link: Link
    total_clicks: int
    bot_clicks: int
    expired_clicks: int
    first_clicked_at: datetime | None
    last_clicked_at: datetime | None
    clicks_per_day: dict[str, int]
    clicks_by_hour: dict[str, int]
    clicks_by_country: dict[str, int]
    clicks_by_device: dict[str, int]
    clicks_by_channel: dict[str, int]
    top_referrers: dict[str, int]


@dataclass(frozen=True, slots=True)
class LinkSummary:
    """One link's headline figure, for listing a campaign."""

    code: str
    url: str
    label: str | None
    total_clicks: int


@dataclass(frozen=True, slots=True)
class CampaignStatistics:
    """What the service knows about every link carrying one campaign name."""

    campaign: str
    links: list[LinkSummary]
    total_clicks: int
    bot_clicks: int
    clicks_by_channel: dict[str, int]
    clicks_by_country: dict[str, int]
    clicks_by_device: dict[str, int]


class CodeAlreadyExistsError(Exception):
    """Raised when a code is already taken."""


class Storage(Protocol):
    """The persistence operations the application needs."""

    def add_link(self, link: Link) -> None: ...

    def get_link(self, code: str) -> Link | None: ...

    def add_click(self, click: Click) -> None: ...

    def get_statistics(self, code: str) -> LinkStatistics | None: ...

    def get_campaign_statistics(self, campaign: str) -> CampaignStatistics | None: ...


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
                    "INSERT INTO links"
                    " (code, url, label, created_at, expires_at, fallback_url, campaign)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        link.code,
                        link.url,
                        link.label,
                        link.created_at.isoformat(),
                        link.expires_at.isoformat() if link.expires_at else None,
                        link.fallback_url,
                        link.campaign,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise CodeAlreadyExistsError(link.code) from error

    def get_link(self, code: str) -> Link | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM links WHERE code = ?", (code,)
            ).fetchone()
        return _row_to_link(row) if row else None

    def add_click(self, click: Click) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO clicks"
                " (code, clicked_at, referrer, country, device, channel, is_bot, after_expiry)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    click.code,
                    click.clicked_at.isoformat(),
                    click.referrer,
                    click.country,
                    click.device,
                    click.channel,
                    int(click.is_bot),
                    int(click.after_expiry),
                ),
            )

    def get_statistics(self, code: str) -> LinkStatistics | None:
        with self._connect() as connection:
            link_row = connection.execute(
                "SELECT * FROM links WHERE code = ?", (code,)
            ).fetchone()
            if link_row is None:
                return None

            # One pass for every headline figure, so the counts cannot disagree with each
            # other the way separate queries against a moving table could.
            totals = connection.execute(
                f"SELECT"
                f"  SUM(CASE WHEN {HUMAN_CLICK} THEN 1 ELSE 0 END) AS humans,"
                f"  SUM(is_bot) AS bots,"
                f"  SUM(after_expiry) AS expired,"
                f"  MIN(CASE WHEN {HUMAN_CLICK} THEN clicked_at END) AS first_at,"
                f"  MAX(CASE WHEN {HUMAN_CLICK} THEN clicked_at END) AS last_at"
                f" FROM clicks WHERE code = ?",
                (code,),
            ).fetchone()

            # Timestamps are stored as ISO 8601, which sorts alphabetically in the same
            # order it sorts chronologically, so slicing the fixed-width prefix groups by
            # date and the one after it by hour. Both are UTC.
            per_day = self._distribution(connection, code, "substr(clicked_at, 1, 10)")
            per_hour = self._distribution(connection, code, "substr(clicked_at, 12, 2)")
            per_country = self._distribution(
                connection, code, "country", ranked=True, skip_nulls=True
            )
            per_device = self._distribution(connection, code, "device", ranked=True)
            per_channel = self._distribution(connection, code, "channel", ranked=True)
            referrers = self._distribution(
                connection,
                code,
                "referrer",
                ranked=True,
                skip_nulls=True,
                limit=TOP_REFERRER_LIMIT,
            )

        return LinkStatistics(
            link=_row_to_link(link_row),
            total_clicks=totals["humans"] or 0,
            bot_clicks=totals["bots"] or 0,
            expired_clicks=totals["expired"] or 0,
            first_clicked_at=_parse_optional(totals["first_at"]),
            last_clicked_at=_parse_optional(totals["last_at"]),
            clicks_per_day=per_day,
            clicks_by_hour=per_hour,
            clicks_by_country=per_country,
            clicks_by_device=per_device,
            clicks_by_channel=per_channel,
            top_referrers=referrers,
        )

    def get_campaign_statistics(self, campaign: str) -> CampaignStatistics | None:
        with self._connect() as connection:
            links = connection.execute(
                "SELECT l.code, l.url, l.label,"
                f" COUNT(CASE WHEN {HUMAN_CLICK} THEN 1 END) AS hits"
                " FROM links l LEFT JOIN clicks c ON c.code = l.code"
                " WHERE l.campaign = ?"
                " GROUP BY l.code, l.url, l.label"
                " ORDER BY hits DESC, l.code",
                (campaign,),
            ).fetchall()
            if not links:
                return None

            totals = connection.execute(
                f"SELECT"
                f"  SUM(CASE WHEN {HUMAN_CLICK} THEN 1 ELSE 0 END) AS humans,"
                f"  SUM(is_bot) AS bots"
                f" FROM clicks WHERE code IN (SELECT code FROM links WHERE campaign = ?)",
                (campaign,),
            ).fetchone()
            per_channel = self._campaign_distribution(connection, campaign, "channel")
            per_country = self._campaign_distribution(
                connection, campaign, "country", skip_nulls=True
            )
            per_device = self._campaign_distribution(connection, campaign, "device")

        return CampaignStatistics(
            campaign=campaign,
            links=[
                LinkSummary(
                    code=row["code"],
                    url=row["url"],
                    label=row["label"],
                    total_clicks=row["hits"],
                )
                for row in links
            ],
            total_clicks=totals["humans"] or 0,
            bot_clicks=totals["bots"] or 0,
            clicks_by_channel=per_channel,
            clicks_by_country=per_country,
            clicks_by_device=per_device,
        )

    @staticmethod
    def _distribution(
        connection: sqlite3.Connection,
        code: str,
        expression: str,
        *,
        ranked: bool = False,
        skip_nulls: bool = False,
        limit: int | None = None,
    ) -> dict[str, int]:
        """Count human clicks for one code, grouped by a column or an expression.

        The expression is composed here from literals in this module, never from input:
        every value reaching SQLite still travels as a bound parameter.
        """
        clause = f" AND {expression} IS NOT NULL" if skip_nulls else ""
        order = "hits DESC, bucket" if ranked else "bucket"
        bound = f" LIMIT {int(limit)}" if limit else ""
        rows = connection.execute(
            f"SELECT {expression} AS bucket, COUNT(*) AS hits FROM clicks"
            f" WHERE code = ? AND {HUMAN_CLICK}{clause}"
            f" GROUP BY bucket ORDER BY {order}{bound}",
            (code,),
        ).fetchall()
        return _buckets(rows)

    @staticmethod
    def _campaign_distribution(
        connection: sqlite3.Connection, campaign: str, column: str, *, skip_nulls: bool = False
    ) -> dict[str, int]:
        """Count human clicks across every link in a campaign, grouped by a column."""
        clause = f" AND {column} IS NOT NULL" if skip_nulls else ""
        rows = connection.execute(
            f"SELECT {column} AS bucket, COUNT(*) AS hits FROM clicks"
            f" WHERE code IN (SELECT code FROM links WHERE campaign = ?)"
            f" AND {HUMAN_CLICK}{clause}"
            f" GROUP BY bucket ORDER BY hits DESC, bucket",
            (campaign,),
        ).fetchall()
        return _buckets(rows)


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

        recorded = [click for click in self.clicks if click.code == code]
        human = _humans(recorded)
        moments = [click.clicked_at for click in human]

        return LinkStatistics(
            link=link,
            total_clicks=len(human),
            bot_clicks=sum(click.is_bot for click in recorded),
            expired_clicks=sum(click.after_expiry for click in recorded),
            first_clicked_at=min(moments, default=None),
            last_clicked_at=max(moments, default=None),
            clicks_per_day=_ordered(
                Counter(click.clicked_at.date().isoformat() for click in human)
            ),
            clicks_by_hour=_ordered(Counter(f"{click.clicked_at.hour:02d}" for click in human)),
            clicks_by_country=_ranked(
                Counter(click.country for click in human if click.country)
            ),
            clicks_by_device=_ranked(Counter(click.device for click in human)),
            clicks_by_channel=_ranked(Counter(click.channel for click in human)),
            top_referrers=_ranked(
                Counter(click.referrer for click in human if click.referrer),
                limit=TOP_REFERRER_LIMIT,
            ),
        )

    def get_campaign_statistics(self, campaign: str) -> CampaignStatistics | None:
        members = [link for link in self.links.values() if link.campaign == campaign]
        if not members:
            return None

        codes = {link.code for link in members}
        recorded = [click for click in self.clicks if click.code in codes]
        human = _humans(recorded)
        per_code = Counter(click.code for click in human)

        summaries = sorted(
            (
                LinkSummary(
                    code=link.code,
                    url=link.url,
                    label=link.label,
                    total_clicks=per_code[link.code],
                )
                for link in members
            ),
            key=lambda summary: (-summary.total_clicks, summary.code),
        )

        return CampaignStatistics(
            campaign=campaign,
            links=summaries,
            total_clicks=len(human),
            bot_clicks=sum(click.is_bot for click in recorded),
            clicks_by_channel=_ranked(Counter(click.channel for click in human)),
            clicks_by_country=_ranked(
                Counter(click.country for click in human if click.country)
            ),
            clicks_by_device=_ranked(Counter(click.device for click in human)),
        )


def _humans(clicks: Iterable[Click]) -> list[Click]:
    return [click for click in clicks if not click.is_bot and not click.after_expiry]


def _row_to_link(row: sqlite3.Row) -> Link:
    return Link(
        code=row["code"],
        url=row["url"],
        label=row["label"],
        created_at=datetime.fromisoformat(row["created_at"]),
        expires_at=_parse_optional(row["expires_at"]),
        fallback_url=row["fallback_url"],
        campaign=row["campaign"],
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
