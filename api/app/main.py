"""FastAPI application. Serves the API and, in production, the built React app.

Run with:  uvicorn --factory app.main:create_app
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes import health
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="Planeswalker HQ",
        version=settings.git_sha,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.state.settings = settings
    app.include_router(health.router)

    # Mounted last, so API routes win. Missing during local API-only work: that is fine.
    if settings.web_dist.is_dir():
        app.mount("/", StaticFiles(directory=settings.web_dist, html=True), name="web")
    return app
