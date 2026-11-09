# URL shortener

A small web service that shortens URLs and reports click analytics, built with FastAPI.
Written as a hiring exercise inside a 3-hour timebox.

![The analytics page showing a seeded campaign](docs/dashboard.png)

## Requirements

- Python 3.13 (3.11 or later works)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Running it locally

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The service listens on `http://localhost:8000`.

- `http://localhost:8000/docs` — interactive API documentation, generated from the code
- `http://localhost:8000/app` — a page for reading a link's performance

To see the page with something in it, seed a demonstration link first:

```bash
uv run python -m scripts.seed_demo
```

Configuration is read from the environment, all of it optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:8000` | The origin used to build the returned short URL |
| `DATABASE_PATH` | `shortener.db` | Where the SQLite file lives |
| `CODE_LENGTH` | `7` | Number of characters in a generated code |
| `DOCS_ENABLED` | `true` | Whether to serve `/docs`, `/redoc` and the OpenAPI schema |
| `RATE_LIMIT` | `30` | Links one client may create per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Length of that window |

## Endpoints

| Method | Path | Behaviour |
| --- | --- | --- |
| `POST` | `/shorten` | Stores a URL. 201 on success, 400 on an invalid or unsafe URL, 409 on a taken or reserved code, 429 past the allowance, 503 if no code could be allocated |
| `GET` | `/{code}` | Redirects with 302 and records the click. 404 if unknown, 410 if expired |
| `GET` | `/stats/{code}` | Reports the destination and the click analytics. 404 if unknown |
| `GET` | `/qr/{code}` | Renders the short link as a PNG QR code. 404 if unknown |
| `GET` | `/app` | The analytics page |

## Example usage

```bash
# Create a short link
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","label":"home"}'
# {"code":"3TBphfZ","short_url":"http://localhost:8000/3TBphfZ","expires_at":null}

# Ask for a readable code, and a date it should stop working
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com/offers","code":"black-friday","expires_at":"2026-12-01T00:00:00Z"}'
# {"code":"black-friday","short_url":"http://localhost:8000/black-friday","expires_at":"2026-12-01T00:00:00Z"}

# Follow it
curl -I localhost:8000/black-friday
# HTTP/1.1 302 Found
# location: https://example.com/offers

# Read the statistics
curl localhost:8000/stats/black-friday
# {
#   "code": "black-friday",
#   "url": "https://example.com/offers",
#   "total_clicks": 268,
#   "first_clicked_at": "2026-10-27T06:08:04Z",
#   "last_clicked_at": "2026-11-09T22:52:36Z",
#   "average_clicks_per_day": 19.14,
#   "clicks_by_hour": {"18": 31, "19": 34, "20": 27, ...},
#   "clicks_by_weekday": {"Mon": 44, "Tue": 29, ...},
#   "clicks_by_country": {"ES": 141, "GB": 47, ...},
#   "clicks_by_device": {"mobile": 169, "desktop": 88, "bot": 11},
#   "top_referrers": {"https://www.instagram.com/": 100, ...}
# }

# Fetch the QR code
curl -o qr.png localhost:8000/qr/black-friday

# A taken or reserved code is refused
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" -d '{"url":"https://example.com","code":"docs"}'
# HTTP/1.1 409 Conflict

# So is a destination inside a private network
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" -d '{"url":"http://169.254.169.254/latest/meta-data/"}'
# HTTP/1.1 400 Bad Request

# An invalid URL, and an unknown code
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" -d '{"url":"not-a-url"}'
# HTTP/1.1 400 Bad Request
curl -I localhost:8000/zzzzzzz
# HTTP/1.1 404 Not Found
```

## Tests

```bash
uv run pytest
uv run ruff check .
uv run mypy app tests scripts
```

67 tests. They drive the application through FastAPI's test client against the in-memory
storage, so the real routes, validation and status codes are exercised without touching a
database file.

## What this service records, and what it does not

The service runs in jurisdictions with different privacy regimes, so it is built to the
strictest of them rather than to each one separately.

- **No IP addresses.** A click records the referrer, a two-letter country code and a
  device category. The country is resolved at the network edge by whatever proxy sits in
  front — `CF-IPCountry` and equivalents — so the application never receives an address.
- **No raw user agents.** The full string is a browser-fingerprinting vector. It is
  reduced at the boundary to bot, mobile, desktop or unknown, which is also the form a
  marketing question actually needs.
- **No cookies and no identifiers.** Nothing is written to the visitor's browser, so the
  service needs no consent banner under the ePrivacy Directive, and there is nothing to
  join one visit to another.
- **Rate limiting without retention.** Clients are keyed by a salted hash of their
  address, held only for the length of the window, with the salt generated per process.

What this costs: the analytics cannot answer anything about individuals or returning
visitors. That is the intended trade.

## Design notes

- **SQLite over in-memory structures.** The brief allowed either. Click analytics that
  disappear on restart answer nothing, so the service persists; the standard library's
  `sqlite3` keeps the dependency list to FastAPI, segno and nothing else.
- **Storage behind a protocol.** Two implementations exist and both are used: SQLite runs
  the service, the in-memory one runs the tests. The abstraction earns its place rather
  than anticipating a need.
- **400 instead of 422 for an invalid URL.** FastAPI answers validation failures with 422,
  which is arguably the more correct status. The brief specifies 400, so a handler remaps
  it; following the stated contract beats being pedantic.
- **Random codes, not a counter or a hash.** A counter leaks how many links exist and
  invites enumeration; hashing the URL makes shortening the same URL twice impossible.
- **Readable custom codes.** Not asked for, but a shortener whose links go into campaigns
  and printed material needs `/black-friday`, not `/3TBphfZ`. Requested codes are checked
  against the paths the service serves itself and against codes already taken.
- **Destinations are checked.** A shortener lends its domain's credibility to whatever it
  points at, so private, loopback and link-local addresses are refused, as are links back
  to the service itself.
- **302, not 301.** A permanent redirect is cached by the browser, so the second click
  from each visitor would never reach the service and the counts would quietly run short.
- **A connection per operation.** FastAPI runs synchronous endpoints in a thread pool,
  where sharing one SQLite connection is unsafe. Opening per call is cheap and correct;
  WAL mode keeps readers from blocking the writer.
- **The page is a client, not a view.** It reads the same public endpoint anyone else
  would, with no build step and no frontend dependencies, so it cannot drift from the API.

## Known limitations

- **Statistics are public.** Anyone holding a code can read its analytics, and a readable
  custom code is by design easy to guess. A management token issued at creation would close
  this; it was left out rather than half-built.
- **No authentication**, so anyone who can reach the service can create links.
- **Aggregations are unbounded.** A link with millions of clicks groups over its whole
  partition of the index on every call. Real traffic needs pagination or a rollup table.
- **Every distribution is in UTC.** "Clicks on Tuesday" means different things in
  different places; carrying the reader's time zone is the correct fix.
- **The redirect reads SQLite on every request**, although the mapping is immutable once
  created and caches perfectly.
- **No schema migrations.** The schema is created on first run and a database file from an
  earlier version is not upgraded.
- **Rate limiting is per process.** Several replicas would each enforce their own
  allowance; a shared store such as Redis is the way out.
- **Destination checks read the host as written.** A public domain that resolves to a
  private address is not caught.

## Where this would go next

The analytics are the part of this service with the most room to grow, and the questions
a marketing team actually asks point the way:

1. **Campaigns.** Links grouped under a campaign, so performance is read per campaign
   rather than per link.
2. **Accounts and ownership.** A `created_by` on each link, which turns the statistics
   from public into private and makes a management view possible.
3. **Rollups.** A table of per-hour totals written as clicks arrive, so the dashboards stop
   aggregating raw rows.
4. **Time-of-day analysis in the reader's zone.** Which, for an energy retailer, is the
   interesting question: when a tariff campaign is engaged with says something about when
   people are willing to shift consumption.
5. **Caching the redirect**, the one change that most affects how this behaves under load.
