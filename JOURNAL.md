# Development journal

Decisions, obstacles and trade-offs, written as they happened rather than reconstructed
afterwards.

| Time | Note |
| --- | --- |
| 21:55 | Started reading the brief |
| 22:00 | The brief asks for FastAPI and REST. Dropped the prepared Django and GraphQL setup; kept the planning files and the tooling conventions |
| 22:00 | No frontend is asked for. FastAPI's generated `/docs` covers exploration, so none was built |
| 22:02 | Requirements extracted into TASKS.md, split into explicit, implied and out of scope |
| 22:03 | Chose SQLite over in-memory dictionaries: analytics that reset on restart answer nothing. Put both behind one protocol so the tests can use the in-memory implementation |
| 22:04 | `POST /shorten` done. FastAPI answers validation failures with 422; the brief says 400, so a handler remaps it |
| 22:05 | Redirect and statistics done. Decided against recording IP addresses: personal data, and the statistics do not need it |
| 22:06 | Wrote the README usage examples and design notes, and the decision log |
| 22:07 | Added readable custom codes as the self-chosen feature, refusing taken and reserved codes with 409 |
| [FILL] | [FILL: entries from the review and verification pass] |

## Known limitations

- The redirect path reads SQLite on every request. The mapping is immutable once created,
  so a cache would remove that read entirely; left out because correctness came first and
  no load justifies it yet.
- Short codes are random with a bounded retry on collision. At the default length of seven
  characters collisions are vanishingly rare, but the retry limit means a saturated code
  space would surface as a 500 rather than a considered error.
- The statistics queries are unbounded. A link with millions of clicks would group over the
  whole table on every call; real use needs either pagination or a rollup table.
- There is no authentication, so anyone who can reach the service can create links and read
  any link's statistics.
