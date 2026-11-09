# Open questions

The brief invites asking rather than guessing. These are the decisions the exercise could
not settle on its own, with what each one changes. Where a question had to be answered to
ship, the assumption taken is written down and the code keeps the other answer cheap.

## Who is allowed to create links?

**Why it matters.** Every question below follows from this one. A shortener open to the
public and one used only by the marketing team are different products with different
threat models.

**Assumed for now.** Anyone who can reach the service, because the brief describes no
actors.

## Should destinations be restricted to the company's own domains?

**Why it matters.** A shortener lends its domain's credibility to whatever it points at.
On an internal tool, an allowlist removes a whole class of abuse: nobody can mint a link
on a trusted domain that leads to a page imitating the company, and a text message
carrying such a link would pass filters a bare unknown domain would not. On a public
shortener an allowlist is impossible, because accepting any valid URL is the product.

**Assumed for now.** Any `http(s)` URL is accepted, as the brief requires. Private,
loopback and link-local addresses are refused, and so are links back to the service, but a
convincing phishing page sits on a perfectly routable host. The allowlist is a
configuration flag away in either direction.

## Should statistics be public, or private to whoever created the link?

**Why it matters.** Today anyone holding a code can read its analytics, and a readable
custom code is by design easy to guess, so a competitor can read a campaign's numbers. A
management token issued at creation would close it, and it earns its keep in three
situations: an agency placing a client's campaign should see its own figures and not a
competitor's; a dealership selling electric vehicles should see its own links and not
another dealership's; and whoever sent a text message to fifty thousand customers with the
wrong destination should be able to repoint it without sending a correction, which matters
more again for a link printed on a bill where there is nothing to resend.

**Assumed for now.** Public, and recorded as a known limitation. Half an authorisation
model is worse than none.

## Are user accounts and an administrative view wanted?

**Why it matters.** This is the full version of the question above: accounts, roles and a
view that lists a team's links rather than looking them up one at a time. It is a
different exercise in size, and it decides whether the token above is a stop-gap or
unnecessary.

**Assumed for now.** Out of scope. The data model leaves room for a `created_by` on a
link, which is where it would start.

## Should unique visitors be counted?

**Why it matters.** It is the figure a marketing team asks for next. Getting it normally
means storing a keyed hash of the client address, which is pseudonymisation and not
anonymisation: IPv4 has about four billion addresses, so with the key in hand every one of
them can be hashed and compared in seconds. Counting unique visitors honestly means
accepting personal data, a retention period and a lawful basis for it.

**Assumed for now.** Not counted, and the reason is in the README. If the business wants
the figure, the question is not technical but who signs off on holding the data.

## How long should click data be kept?

**Why it matters.** Nothing currently expires. A retention period is the other half of any
answer about personal data, and it also bounds how large the aggregations can get.

**Assumed for now.** Kept indefinitely, which is a decision by default rather than a
decision.

## Which time zone should the analytics report in?

**Why it matters.** Every distribution here is UTC. "Clicks on Tuesday" and "clicks at
19:00" mean different things in Madrid, London and Melbourne, and a campaign is usually
read by someone in one particular place.

**Assumed for now.** UTC, stated on the page and in the README rather than guessed at.

## What traffic should the service be built for?

**Why it matters.** The redirect reads SQLite on every request and the aggregations scan a
link's whole partition of the index. At the volume of an exercise neither matters; at the
volume of a national campaign both do, and the fixes differ — caching the redirect, a
rollup table for the statistics.

**Assumed for now.** Correctness first, with both left as known limitations rather than
pre-optimised.

## Is there an existing campaign taxonomy to align with?

**Why it matters.** Campaigns are free text here. If marketing already names campaigns a
particular way, or already has UTM conventions, the field should match them so the figures
reconcile with whatever analytics the destination pages use.

**Assumed for now.** Free text, with tracking parameters carried through untouched.

## Should an expired link redirect, or refuse?

**Why it matters.** Both are defensible, and which is right depends on where the link
lives. A link printed on a bill keeps circulating, so sending those people to the tariff
listing serves them better than an error.

**Assumed for now.** Configurable per link: a fallback redirects, no fallback answers 410.

## Should short codes be case-sensitive?

**Why it matters.** They are today, so `/Summer` and `/summer` are different links. That
follows most shorteners, but it surprises people reading a code off a poster.

**Assumed for now.** Case-sensitive, with reserved names matched case-insensitively so no
casing of `docs` can be claimed.

## Where will this run, and is there a CDN in front of it?

**Why it matters.** The country attached to a click is read from a header that a content
delivery network sets. With no proxy in front, the country is simply unknown — which the
service reports honestly, but it means the geography in the analytics depends on the
deployment rather than on the code.

**Assumed for now.** A proxy that sets one of the usual headers. The service never reads
an IP address itself, by design.
