# Decision log

Short record of the technical choices made, the alternatives considered, and the
reasoning. Kept brief on purpose: this is a 3-hour exercise, not an architecture review.

## 1. Django 5.2 LTS rather than 6.1

**Alternative:** Django 6.1.3, the latest stable release.

**Why:** `strawberry-graphql-django` declares support for Django 5.2 and 6.0, not yet
6.1. Running on an undeclared combination is a risk with no upside here. 5.2 is the
current LTS, with security support until April 2028.

## 2. Strawberry rather than Graphene for GraphQL

**Alternative:** `graphene-django`, more widely adopted and with a larger install base.

**Why:** Strawberry derives the schema from standard Python type annotations, so `mypy`
verifies the API layer rather than treating it as opaque. Graphene keeps a parallel type
system of its own and leans on implicit conventions such as `resolve_*` method names.
Strawberry is also the more actively maintained of the two.

## 3. SQLite behind `DATABASE_URL` rather than PostgreSQL with Docker

**Alternative:** PostgreSQL in `docker-compose`, closer to a production setup.

**Why:** A reviewer should be able to clone and run this without Docker. The database is
configured from a single environment variable, so pointing it at PostgreSQL is a
one-line change with no code touched. Nothing in this exercise depends on
PostgreSQL-specific behaviour.

## 4. Two directories rather than a monorepo

**Alternative:** pnpm workspaces with `apps/` and `packages/`.

**Why:** A monorepo earns its tooling when code is shared across several applications.
There is one frontend here. Adding workspace configuration would be complexity without a
problem to solve.

## 5. A small fetch-based GraphQL client rather than Apollo

**Alternative:** Apollo Client or urql.

**Why:** The frontend makes a handful of queries and needs no normalised cache, optimistic
updates or subscriptions. A short typed wrapper around `fetch` covers it and leaves
nothing unexplained in the dependency tree.

## 6. [FILL: domain modelling decision]

**Alternative:** [FILL]

**Why:** [FILL]

## 7. [FILL: a decision forced by the time limit]

**Alternative:** [FILL]

**Why:** [FILL]
