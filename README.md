# [FILL: project name]

[FILL: one sentence saying what this does and for whom.]

Built as a technical exercise in a 3-hour timebox.

## Starting point

The project wiring in the first commit was prepared ahead of the exercise: the Django and
Next.js setup, the tooling configuration and these process files. The domain model, the
API and the UI were built within the timebox.

## Stack

- **Backend:** Python 3.13, Django 5.2 LTS, Strawberry GraphQL, SQLite (swappable via `DATABASE_URL`)
- **Frontend:** Next.js 16 (App Router), TypeScript, Tailwind CSS
- **Tooling:** uv, ruff, mypy, pytest

## Getting started

Two terminals. Backend:

```bash
cd backend
cp .env.example .env
uv sync
uv run python manage.py migrate
uv run python manage.py seed
uv run python manage.py runserver
```

Frontend:

```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev
```

The app is served at http://localhost:3000 and the GraphQL endpoint, with GraphiQL
enabled in development, at http://localhost:8000/graphql/

## Scope

### What is implemented

- [FILL: one line per delivered capability]

### What was deliberately left out

- [FILL: what you chose not to build, and why it was the right call for an MVP]

### What I would do next

- [FILL: the first things you would add with more time]

## Assumptions

The brief left some points open. These are the readings I went with:

- [FILL: assumption, and the reasoning behind it]

## Architecture

[FILL: a short paragraph on how the pieces fit and where the business logic lives.]

Layout:

```
backend/
  config/     Django project: settings, URLs, ASGI entry point
  core/       Shared building blocks (abstract base model, schema root)
  [FILL]/     Domain app
frontend/
  src/app/    App Router pages
  src/lib/    GraphQL client
```

## Testing

```bash
cd backend
uv run pytest
uv run ruff check .
uv run mypy .
```

[FILL: one line on what the tests cover and why those cases.]

## Screenshots

[FILL: two or three images of the running app.]
