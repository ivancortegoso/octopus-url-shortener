"""Persistence for links and clicks.

The brief offered either SQLite or in-memory Python structures. Both are here behind one
protocol: SQLite backs the running service, because click analytics that vanish on
restart answer nothing, and the in-memory implementation keeps the tests free of files.
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
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL REFERENCES links(code),
    clicked_at TEXT NOT NULL,
    referrer   TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS clicks_by_code ON clicks(code);
"""


@dataclass(frozen=True, slots=True)
class LinkStatistics:
    """What the service knows about one short code."""

    link: Link
    total_clicks: int
    last_clicked_at: datetime | None
    clicks_per_day: dict[str, int]
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
        """
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            yield connection
            connection.commit()
        finally:
            connection.close()

    def add_link(self, link: Link) -> None:
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO links (code, url, label, created_at) VALUES (?, ?, ?, ?)",
                    (link.code, link.url, link.label, link.created_at.isoformat()),
                )
            except sqlite3.IntegrityError as error:
                raise CodeAlreadyExistsError(link.code) from error

    def get_link(self, code: str) -> Link | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT code, url, label, created_at FROM links WHERE code = ?", (code,)
            ).fetchone()
        return _row_to_link(row) if row else None

    def add_click(self, click: Click) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO clicks (code, clicked_at, referrer, user_agent) VALUES (?, ?, ?, ?)",
                (click.code, click.clicked_at.isoformat(), click.referrer, click.user_agent),
            )

    def get_statistics(self, code: str) -> LinkStatistics | None:
        with self._connect() as connection:
            link_row = connection.execute(
                "SELECT code, url, label, created_at FROM links WHERE code = ?", (code,)
            ).fetchone()
            if link_row is None:
                return None

            totals = connection.execute(
                "SELECT COUNT(*) AS total, MAX(clicked_at) AS last FROM clicks WHERE code = ?",
                (code,),
            ).fetchone()
            per_day = connection.execute(
                "SELECT substr(clicked_at, 1, 10) AS day, COUNT(*) AS hits"
                " FROM clicks WHERE code = ? GROUP BY day ORDER BY day",
                (code,),
            ).fetchall()
            referrers = connection.execute(
                "SELECT referrer, COUNT(*) AS hits FROM clicks"
                " WHERE code = ? AND referrer IS NOT NULL"
                " GROUP BY referrer ORDER BY hits DESC LIMIT 5",
                (code,),
            ).fetchall()

        return LinkStatistics(
            link=_row_to_link(link_row),
            total_clicks=totals["total"],
            last_clicked_at=datetime.fromisoformat(totals["last"]) if totals["last"] else None,
            clicks_per_day={row["day"]: row["hits"] for row in per_day},
            top_referrers={row["referrer"]: row["hits"] for row in referrers},
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
        referrers = Counter(click.referrer for click in clicks if click.referrer)

        return LinkStatistics(
            link=link,
            total_clicks=len(clicks),
            last_clicked_at=max((click.clicked_at for click in clicks), default=None),
            clicks_per_day=dict(
                sorted(Counter(click.clicked_at.date().isoformat() for click in clicks).items())
            ),
            top_referrers=dict(referrers.most_common(5)),
        )


def _row_to_link(row: sqlite3.Row) -> Link:
    return Link(
        code=row["code"],
        url=row["url"],
        label=row["label"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
