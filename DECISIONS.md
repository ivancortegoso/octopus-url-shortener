# Decision log

The choices made during the exercise, the alternatives considered and the reasoning.
Short on purpose: three hours of work does not justify an architecture dossier.

## 1. SQLite rather than Python data structures

**Alternative:** the brief's "MVP" option — dictionaries held in memory.

**Why:** the service exists to report click analytics, and analytics that reset whenever
the process restarts cannot answer anything useful. SQLite through the standard library's
`sqlite3` costs no extra dependency and gives durability, so the cheaper option saved
nothing worth having.

## 2. Storage behind a protocol, with two implementations

**Alternative:** calling `sqlite3` directly from the route handlers.

**Why:** the brief named two storage strategies, so an interface between the application
and its storage is responsive to the problem rather than speculative. Both
implementations are live: SQLite backs the running service and the in-memory one backs
the tests, which is what keeps the abstraction honest. One implementation and an
interface would have been over-engineering.

## 3. Invalid URLs answer 400, not 422

**Alternative:** leaving FastAPI's default 422 and noting the discrepancy.

**Why:** the brief specifies 400. An exception handler remaps validation failures rather
than hand-rolling URL validation in the route, so Pydantic still does the parsing. 422 is
arguably the more accurate status for a well-formed body that fails validation, but a
stated contract beats a pedantic one.

## 4. Randomly generated codes

**Alternative:** an incrementing counter encoded in base62, or a hash of the URL.

**Why:** a counter publishes how many links the service holds and makes neighbouring
links guessable. Hashing the URL means the same URL always maps to the same code, which
removes the ability to shorten one URL twice with different labels. Random codes avoid
both; collisions are handled by retrying a bounded number of times rather than assumed
away.

## 5. No IP addresses in the click record

**Alternative:** storing the client IP, as click analytics commonly do.

**Why:** an IP address is personal data under the GDPR, and none of the questions these
statistics answer need one. Referrer and user agent cover the analytical value without
taking on the obligation. A real product would decide this with a retention policy, not
by default.

## 6. A SQLite connection per operation

**Alternative:** one long-lived connection on the application state.

**Why:** FastAPI runs synchronous endpoints in a worker thread pool, and a single
`sqlite3` connection is not safe to share across threads. Opening a connection per
operation is cheap, removes the concurrency question entirely, and WAL mode keeps reads
from blocking the write.

## 7. No frontend

**Alternative:** a small page to demonstrate the flow.

**Why:** the brief asks for a web service and lists code, a README and tests as the
deliverables. FastAPI generates interactive documentation at `/docs` from the same type
annotations that validate the requests, which covers exploration without a line of
frontend code.

## 8. Country resolved at the edge, never from an IP address

**Alternative:** reading the client address and resolving it to a country in the
application, either with a bundled GeoIP database or a lookup service.

**Why:** both alternatives mean the application receives and processes an IP address, and
a lookup service means sending it to a third party on the hot path. Content delivery
networks already resolve geography before the request arrives and pass it in a header, so
the application can take a two-letter code and nothing else. A country code on its own
singles out nobody. The cost is a dependency on the deployment: with no proxy in front,
the country is simply unknown, which the response represents honestly.

## 9. A device category instead of the user agent

**Alternative:** storing the user agent string, as click analytics usually do.

**Why:** the full string is one of the strongest browser-fingerprinting signals there is,
and nothing a marketing team asks needs it. Reducing it at the boundary to bot, mobile,
desktop or unknown answers the real question — how people arrive — and leaves nothing
behind worth correlating. The classification is a heuristic, which the code says plainly:
user agents are self-reported and imitate each other.

## 10. 410 for expired links rather than 404

**Alternative:** treating an expired link as if it had never existed.

**Why:** 410 Gone says the resource existed and will not return, which is exactly the
situation and lets a caller distinguish a typo from a campaign that has finished. The
statistics stay readable after expiry, because the point of an expiring campaign link is
to look at how it did once it is over.

## 11. Statistics stay public

**Alternative:** issuing a management token when a link is created and requiring it to read
the statistics.

**Why:** the brief describes no actors and asks for an MVP. A token would close a real gap
— readable custom codes are easy to guess, so a competitor could read a campaign's
numbers — but half of an authorisation model is worse than none, and a full one is a
different exercise. It is recorded as a known limitation instead, with ownership as the
next step.

## 12. The page is a client of the API, not a view rendered by it

**Alternative:** server-rendered templates with Jinja2, which FastAPI supports.

**Why:** a page that reads the same public endpoint as any other client cannot drift from
the API, needs no templating dependency, and demonstrates that the API is usable. It is
one static file with no build step. The brief asked for a web service; this is there to
show the analytics to someone who does not read JSON, and nothing depends on it.

## 13. Automated resolutions counted apart, not discarded

**Alternative:** counting every resolution as a click, or dropping the automated ones.

**Why:** both mislead. A total that includes link checkers and the preview fetches chat
apps make overstates what a campaign achieved; one that silently drops them hides that a
link is being fetched at all, which is itself worth knowing. Two signals identify them
cheaply: a HEAD request asks where a code leads without opening it, and a user agent may
name itself. It is a heuristic and the code says so, because user agents are self-reported.

## 14. A channel marker on the QR code

**Alternative:** one code per channel, so a poster and a text message use different links.

**Why:** separate codes would answer the same question, but they fragment the link: the
same campaign placement then has two sets of statistics to add up, and two QR codes to keep
straight. Encoding the marker in what the QR contains keeps one code with one report, and
the marker is stripped before the redirect so the destination never sees it.

## 15. A fallback destination instead of a bare 410

**Alternative:** answering 410 for every expired link.

**Why:** a short link printed on a bill or a poster keeps circulating long after the
campaign behind it ends, and sending those people to the tariff listing serves them better
than an error page. The resolutions that arrive after expiry are recorded separately, so
the campaign's figures stay honest while still showing that the printed copy is working.
410 remains the answer when no fallback was set, because then there is genuinely nowhere
to send anyone.

## 16. No unique-visitor count

**Alternative:** storing a keyed hash of the client address, the usual way this is done.

**Why:** hashing an IP address is pseudonymisation, not anonymisation. IPv4 has about four
billion addresses, so with the key in hand every one of them can be hashed and compared in
seconds; the GDPR treats the result as personal data for exactly that reason, and rotating
the key daily narrows the window without changing the category. Counting unique visitors
honestly means accepting personal data, a retention policy and a lawful basis. For an
exercise whose whole analytics story is that it holds none, that trade is not worth making,
so the figure is absent and the reason is written down.

## 17. A campaign is a label on a link

**Alternative:** a campaigns table with links referencing it.

**Why:** at this size the label answers the question — which placement brought the traffic —
with one indexed column and no second table to create, join or migrate. The moment a
campaign needs properties of its own, a budget or an owner or a date range, it becomes an
entity and this becomes a foreign key. Reaching for the table first would be building for a
requirement nobody has stated.

## 18. The page borrows the palette, and nothing else

**Alternative:** a neutral theme, or a full imitation including the logo and the favicon.

**Why:** the colours octopusenergy.es publishes in its own stylesheet are read off the site
and used here, so the tool sits comfortably beside the product it would serve, and the
twelve-pixel corner radius comes from the same place. What is not borrowed is the mark: no
logo, no wordmark, no favicon of theirs, and the icon in the tab is drawn for this project.
Their typeface, Chromatophore, is proprietary, and their own stylesheet falls back to
Helvetica when it is unavailable, which is exactly what happens here.

The line is deliberate. A tool wearing someone's mark reads as their property, and a
screenshot of it would travel as if it were. Matching the palette shows the work was done
with the reader in mind; copying the mark would claim something that is not mine to claim.

## 19. The page builds its own markup from nodes, not from strings

**Alternative:** assembling the line under the destination with `innerHTML`, which is how
it was written first.

**Why:** the campaign name and the fallback URL are chosen by whoever creates a link, and
the first version interpolated them straight into `innerHTML`. A link created with a
campaign of `<img src=x onerror=...>` would then have run script in the browser of anyone
who opened its report — a stored cross-site scripting hole, in the tool rather than the
API. Building the line from DOM nodes with `textContent` cannot inject, whatever the value
holds, and it is also what made the campaign pill a working link rather than a styled span.

The API was never the problem: it returns JSON, and JSON carries no markup. The hole was
in how the page chose to render it, which is where this class of bug usually lives.

## 20. A failed resolution answers a page or a payload, depending on who asked

**Alternative:** one answer for everyone — JSON, as the rest of the API returns.

**Why:** the redirect is the only route a person lands on directly. Someone who follows an
expired link from a printed poster gets a raw `{"detail": "This link has expired."}`, which
tells them nothing and looks broken. A link checker, meanwhile, needs the machine-readable
answer. Browsers name `text/html` in what they accept and programs send `*/*` or ask for
JSON, so the two can be told apart without guessing: the status code is the same either
way, only its clothing differs.

The distinction is deliberately limited to that one route. `/stats` and `/qr` are consumed
by programs, including this project's own page, and answer with a payload regardless.

## 21. The form reports its own validation, and the error pages carry the header

**Alternative:** the browser's built-in validation bubble.

**Why:** the bubble is drawn by the browser, in the browser's interface language rather
than the page's, in a style no stylesheet reaches, and showing it makes the browser scroll
the page to anchor it. Marking the form `novalidate` keeps the constraints — they still
drive each field's validity — while the page says what is wrong, beside the field, in its
own words, clearing as soon as the field is touched. `aria-invalid` and the message beside
the input carry the same information to a screen reader.

Escaping the hyphen in that field's pattern is not cosmetic. A `pattern` attribute is
compiled with the regular expression `v` flag, under which a bare hyphen at the end of a
character class does not compile — and a pattern that fails to compile is dropped by the
browser in silence, so every value passed. The server's own check was unaffected, because
Python's regular expressions accept the bare hyphen, which is exactly why it went unnoticed:
bad input was refused, just one layer later than intended.

The two failure pages carry the header as well, so someone who lands on one can reach the
tool rather than reaching a dead end. That is right while the service has no accounts;
once a link belongs to someone, a page shown to the public should not advertise the tool
that created it.

## 22. Liveness and readiness are separate, and neither reports timings

**Alternative:** one health endpoint that checks the database and reports response times.

**Why:** they answer different questions and a single endpoint cannot serve both. A liveness
check decides whether to restart the process, so it must not depend on anything downstream:
consult the database there and a blip in it reads as a dead application, answered by a
restart that mends nothing — and across several replicas, one blip becomes a restart storm.
`/health` therefore reports only that the process is answering. `/ready` does consult the
database, because a failing readiness check takes the instance out of rotation without
killing it, which is the correct response to a dependency that has stopped answering.

Timings belong in neither. An average held by the application is a figure it has to keep
state for, describes one instant, and is measured better from outside. Each request already
records its own duration in the access log, and a `/metrics` endpoint for scraping is the
next step rather than a fatter health check.
