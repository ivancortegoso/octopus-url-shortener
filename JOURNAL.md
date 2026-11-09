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
| 22:10 | Three tests caught the custom-code feature not being wired into the route. Fixed, and the commit that carried it was incomplete, so it was redone |
| 22:20 | Reviewed the service against how it would be abused and found four issues: open redirects to private addresses, no rate limiting, a 500 on code exhaustion, and documentation always exposed |
| 22:40 | Hardened all four. Rate-limit clients are keyed by a salted hash rather than their address, so no raw IP is held even in memory |
| 22:50 | Added expiry, and the analytics a campaign actually needs. Country comes from the edge as a two-letter code and the user agent is reduced to a device category, so no personal data is stored |
| 23:05 | Added the QR endpoint and a page that reads the public statistics endpoint, plus a seeding script so the page has something to show |
| 23:10 | Added request correlation, JSON access logs and a health endpoint |
| 23:12 | Separated automated resolutions from real ones, and found that HEAD was answering 405 — which contradicted the brief's own `curl -I` example |
| 23:14 | Added campaigns, the channel marker on QR codes, fallback destinations and tracking-parameter forwarding |
| 23:16 | Decided against counting unique visitors: a hashed IPv4 address is reversible by exhaustion, so it would have made the privacy claim false |
| 23:20 | Left the destination allowlist out as an open question for the business, since it depends on who may create links |
| 23:25 | Dressed the page in the palette octopusenergy.es publishes, without its logo, wordmark or favicon |
| 23:30 | Made each placement in a campaign a link to its own report, and the campaign pill a link back |
| 23:32 | Found stored XSS in the page while doing that: the campaign name went into innerHTML, and the name is chosen by whoever creates the link. Rebuilt the line from DOM nodes and confirmed with an injected campaign that nothing executes |
| 23:35 | Put the figure on each bar behind a hover, and made the bar being pointed at sit above the ones beside it rather than behind them |
| 23:40 | Added the start page: the lookup and a create form, a masthead and navigation, so the service can be shown to someone who will not use curl |
| 23:45 | Reworded every label and hint for the person using the tool rather than the person who wrote it, and moved the explanations behind an info icon so the form stays short |
| 23:50 | Found the create form's code pattern silently dead: a trailing hyphen in the character class fails to compile under the regex `v` flag, so the browser drops the attribute without saying so and anything validated. Escaped it, and said why in the markup |
| 23:52 | Replaced the browser's own validation bubble with per-field messages in the form's wording; the server already repeated every check, so nothing moved out of the API |
| 23:55 | Fixed an expiry landing an hour or two out: the picker reads the local clock and the value was being sent as though it were UTC |
| 00:00 | Added the page for an expired link and the page for an unknown code, chosen by the Accept header so a program still gets JSON |
| 00:10 | Split readiness from liveness: `/health` answers without consulting anything, `/ready` consults the database and answers 503 when it cannot |

## Known limitations

Carried in the README, which is where a reader will look for them.
