# Task breakdown

Work is sliced vertically: each slice delivers one endpoint end to end — storage, domain
rule, route and test — and leaves something that can be demonstrated with curl. Nothing
is "all the models, then all the routes": a horizontal slice leaves nothing to show if
time runs out.

## Definition of done

A slice is done when all four hold:

- its tests pass
- `ruff` and `mypy` are clean
- the behaviour is reachable over HTTP and documented in the README
- it is committed

## Timebox

| Time | Block |
| --- | --- |
| 0:00-0:20 | Read the brief, extract requirements, write scope and assumptions |
| 0:20-0:30 | Model the domain and choose the storage strategy |
| 0:30-2:30 | Vertical slices |
| 2:30 | Feature freeze |
| 2:30-2:45 | Design notes and known limitations |
| 2:45-3:00 | Clean clone, follow the README, confirm it runs |

If anything blocks for more than 10 minutes: ship the simplest thing that works, record
it as a known limitation, move on.

## Requirements from the brief

### Explicit

- [x] `POST /shorten` accepts `{"url": "<valid http(s) URL>", "label": "optional string"}`
- [x] `POST /shorten` returns `{"code": "abc123", "short_url": "http://localhost:8000/abc123"}`
- [x] `GET /{code}` redirects with 302 to the original URL
- [x] `GET /{code}` records a click event
- [x] `GET /stats/{code}` returns the original URL, the total click count and any further
      recorded information worth exposing
- [x] Invalid URL returns 400
- [x] Unknown code returns 404
- [x] README with local run instructions, example curl commands and 5-10 lines of design notes
- [x] A couple of minimal pytest tests, shortening and redirect among them
- [x] Python 3.11+ and FastAPI
- [ ] Code in a GitHub repository

### Implied

- [x] Short codes must be unique, and collisions handled rather than assumed away
- [ ] The redirect path must stay cheap: it is the hot path of the service
- [x] Click data must survive a restart for the analytics to mean anything
- [x] Reserved paths (`/docs`, `/stats`, `/health`) must not be claimable as short codes

### Out of scope

- Authentication and per-user link ownership: the brief describes no actors
- A frontend: the brief asks for a web service, and FastAPI's OpenAPI UI covers exploration
- Deployment, containers and CI

## Slices

### Slice 1 - Create a short link

- [x] Domain: short code generation with collision handling
- [x] Storage: persist a link
- [x] `POST /shorten` with URL validation returning 400
- [x] Tests: happy path and a rejected URL

### Slice 2 - Redirect and record the click

- [x] `GET /{code}` returning 302, and 404 for an unknown code
- [x] Storage: append a click event
- [x] Tests: redirect target, 404, and that the click is recorded

### Slice 3 - Expose the statistics

- [x] `GET /stats/{code}` with the original URL and the click total
- [x] The further analytics worth exposing
- [x] Tests: counts reflect the clicks recorded

### Slice 4 - One feature of our own: readable custom codes

- [x] Optional `code` in the request, validated for shape
- [x] 409 for a code already taken or reserved by the service
- [x] Tests for the happy path and each refusal
