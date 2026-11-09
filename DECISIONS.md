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
