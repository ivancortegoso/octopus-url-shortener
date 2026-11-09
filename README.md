# URL shortener

A small web service that shortens URLs and reports basic click analytics, built with
FastAPI. Written as a hiring exercise inside a 3-hour timebox.

## Requirements

- Python 3.13 (3.11 or later works)
- [uv](https://docs.astral.sh/uv/) for dependency management

## Running it locally

```bash
uv sync
uv run uvicorn app.main:app --reload
```

The service listens on `http://localhost:8000`. Interactive API documentation, generated
from the code, is at `http://localhost:8000/docs`.

Configuration is read from the environment, all of it optional:

| Variable | Default | Purpose |
| --- | --- | --- |
| `BASE_URL` | `http://localhost:8000` | The origin used to build the returned short URL |
| `DATABASE_PATH` | `shortener.db` | Where the SQLite file lives |
| `CODE_LENGTH` | `7` | Number of characters in a generated code |

## Endpoints

| Method | Path | Behaviour |
| --- | --- | --- |
| `POST` | `/shorten` | Stores a URL, returns its code and short URL. 201 on success, 400 on an invalid URL |
| `GET` | `/{code}` | Redirects with 302 to the original URL and records the click. 404 if the code is unknown |
| `GET` | `/stats/{code}` | Reports the original URL and the click analytics. 404 if the code is unknown |

## Example usage

```bash
# Create a short link
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com","label":"home"}'
# {"code":"3TBphfZ","short_url":"http://localhost:8000/3TBphfZ"}

# Follow it
curl -I localhost:8000/3TBphfZ
# HTTP/1.1 302 Found
# location: https://example.com/

# Read the statistics
curl localhost:8000/stats/3TBphfZ
# {
#   "code": "3TBphfZ",
#   "url": "https://example.com/",
#   "label": "home",
#   "created_at": "2026-11-09T21:03:57.758141Z",
#   "total_clicks": 1,
#   "last_clicked_at": "2026-11-09T21:03:57.763018Z",
#   "clicks_per_day": {"2026-11-09": 1},
#   "top_referrers": {"https://news.example": 1}
# }

# An invalid URL is rejected
curl -X POST localhost:8000/shorten \
  -H "Content-Type: application/json" -d '{"url":"not-a-url"}'
# HTTP/1.1 400 Bad Request

# An unknown code is not found
curl -I localhost:8000/zzzzzzz
# HTTP/1.1 404 Not Found
```

## Tests

```bash
uv run pytest
uv run ruff check .
uv run mypy app tests
```

The tests drive the application through FastAPI's test client against the in-memory
storage, so they exercise the real routes, validation and status codes without touching a
database file.

## Design notes

- **SQLite over in-memory structures.** The brief allowed either. Click analytics that
  disappear on restart answer nothing, so the service persists; the standard library's
  `sqlite3` keeps the dependency list to FastAPI alone.
- **Storage behind a protocol.** Two implementations exist and both are used: SQLite runs
  the service, the in-memory one runs the tests. The abstraction earns its place rather
  than anticipating a need.
- **400 instead of 422 for an invalid URL.** FastAPI answers validation failures with 422,
  which is arguably the more correct status. The brief specifies 400, so a handler remaps
  it; following the stated contract beats being pedantic.
- **Random codes, not a counter or a hash.** A counter leaks how many links exist and
  invites enumeration; hashing the URL makes shortening the same URL twice impossible.
- **No IP addresses.** Clicks record the referrer and the user agent. An IP is personal
  data under the GDPR and none of these statistics need it.
- **A connection per operation.** FastAPI runs synchronous endpoints in a thread pool,
  where sharing one SQLite connection is unsafe. Opening per call is cheap and correct;
  WAL mode keeps readers from blocking the writer.

## What I would add next

- **Caching on the redirect path.** It is the hot path and currently hits SQLite on every
  request. The mapping is immutable once created, so it caches perfectly.
- **Expiry.** An `expires_at` column and a 410 for links past it.
- **Rate limiting per IP** on `POST /shorten`, to stop the code space being farmed.
- **Pagination of the analytics**, and clicks per hour rather than per day for recent links.
- **A `created_by` owner and authentication**, which is what any real deployment needs
  before it can let anyone delete or edit a link.
