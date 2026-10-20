# One image for API and web app: stage 1 builds the React app, stage 2 is the Python
# runtime that serves the API and the built files.

# --- Stage 1: build the React app ------------------------------------------------------
FROM node:24.21.0-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# --- Stage 2: Python runtime -----------------------------------------------------------
FROM python:3.12.14-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.11.16 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1

WORKDIR /app/api
# Dependencies first: this layer stays cached until the lock file changes.
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY api/ ./
COPY db/ /app/db/
COPY --from=web /web/dist /app/web/dist

RUN useradd --system --no-create-home --uid 10001 app
USER app

# Set by the build (CI passes the commit SHA); /health reports it.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA WEB_DIST=/app/web/dist

EXPOSE 8000
CMD ["uvicorn", "--factory", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000"]
