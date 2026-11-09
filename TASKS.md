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

### Slice 5 - Close what a review of the attack surface found

- [x] Refuse destinations inside private, loopback and link-local ranges
- [x] Refuse destinations pointing back at the service
- [x] Rate limit link creation per client, keyed by a salted hash
- [x] Answer 503 rather than 500 when no code can be allocated
- [x] Make serving the generated documentation a configuration choice

### Slice 6 - Expiry and the analytics a campaign needs

- [x] Optional `expires_at`, refused when already past, 410 once reached
- [x] Country from the network edge as a two-letter code, validated not trusted
- [x] Device category in place of the raw user agent
- [x] First click, daily average, and distributions by hour, weekday, country and device
- [x] Weekday and average derived in the domain so the storage implementations agree

### Slice 7 - Something to show

- [x] `GET /qr/{code}` rendering the short link as a PNG
- [x] A page at `/app` reading the public statistics endpoint
- [x] A seeding script so the page has a populated link to display

### Slice 8 - Being able to see what the service is doing

- [x] A correlation id per request, returned to the caller and carried into every log line
- [x] One JSON access log line per request: method, path, status and duration
- [x] `GET /health` as a liveness check that consults nothing
- [x] Automated resolutions counted apart from real ones
- [x] `HEAD` answered rather than refused, which the brief's own `curl -I` example assumes

### Slice 9 - A campaign, not just a link

- [x] Optional `campaign` on a link, and `GET /stats/campaign/{campaign}` ranking placements
- [x] A channel marker on the QR image, so a scan is distinguishable from a tap
- [x] Tracking parameters carried from the short link to the destination
- [x] An optional fallback destination, used once a link has expired

### Slice 10 - Something a marketing team could be shown

- [x] A start page: create a short link, or look up a link or a campaign
- [x] Each placement in a campaign a link to its own report, and the campaign a link back
- [x] Per-field validation in the page's own wording, and the hints behind an info icon
- [x] The palette octopusenergy.es publishes, without its logo, wordmark or favicon

### Slice 11 - What a failed resolution looks like

- [x] A page for an expired link, and a page for an unknown code
- [x] A browser gets the page and a program gets JSON, decided by the `Accept` header
- [x] `GET /ready`, which does consult the database and answers 503 when it cannot

## Not built, and why

- **Bulk creation**, on the brief's list of nice-to-haves: it changes nothing about what
  the service demonstrates and adds surface to defend.
- **A management token on the statistics**: the right fix for public analytics, but half an
  authorisation model is worse than none. Recorded as a limitation instead.
- **Accounts, roles and an administrative view**: a different exercise, and the brief asks
  for an MVP. Sketched in the README under where this would go next.
