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
