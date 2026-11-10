# Planeswalker HQ

A personal manager for a Magic: The Gathering collection and decks.

This is a learning project: Postgres with hand-written SQL, FastAPI, React, and a full
development workflow (pull requests, CI, dev and prod environments). Planning notes live
outside this repository.

## Layout

```
api/        FastAPI app (Python 3.12, uv, psycopg 3) — hand-written SQL in app/queries/
db/         migrations/NNNN_name.sql and migrate.py, the forward-only runner
web/        React + TypeScript + Vite + Tailwind + shadcn/ui + TanStack Query
Dockerfile  one image: builds the React app, then serves API and web app with uvicorn
```

## Local development

Everything at once, as it will run on the server:

```bash
GIT_SHA=$(git rev-parse HEAD) docker compose -f compose.dev.yml up --build
```

Then open http://localhost:8000. `/health` reports the running version and the newest
applied migration; the API docs are at `/api/docs`.

Working on one side only:

```bash
docker compose -f compose.dev.yml up -d db      # Postgres on localhost:5433
cd api && uv run pytest                         # each test gets its own fresh database
cd web && npm run dev                           # Vite on :5173, proxies /health and /api to :8000
```

## Migrations

`db/migrate.py` applies every file in `db/migrations/` that has not run yet, in version
order, each in its own transaction, and records its SHA-256 checksum in
`schema_migrations`.

- **Never edit a migration that has run.** The runner refuses to continue if an applied
  file changed. Write a new migration instead.
- **Only forward.** A new file needs a higher number than every applied one.
- **Expand, then contract.** For a moment during each deploy the old code runs against
  the new schema, so every migration must work with both. Drop or rename a column at the
  earliest one release after no code uses it any more.

## Checks

CI runs on every pull request: ruff and pytest (against a fresh Postgres, all migrations
from zero) for the API; ESLint, TypeScript, Vitest and the build for the web app.
