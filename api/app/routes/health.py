"""GET /health: is the API up, which version runs, and how far is the database migrated.

The deploy script polls this endpoint after a restart and compares "version" with the Git
SHA it just deployed.
"""

import logging
from typing import Literal

import psycopg
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app import db
from app.settings import Settings

logger = logging.getLogger(__name__)
router = APIRouter()


class MigrationInfo(BaseModel):
    version: int
    name: str


class Health(BaseModel):
    status: Literal["ok", "error"]
    version: str
    database: Literal["ok", "unreachable"]
    migration: MigrationInfo | None


def _current_migration(conn: psycopg.Connection) -> MigrationInfo | None:
    try:
        row = conn.execute(db.query("current_migration")).fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    return MigrationInfo(version=row[0], name=row[1]) if row else None


@router.get("/health", responses={503: {"model": Health}})
def health(request: Request, response: Response) -> Health:
    settings: Settings = request.app.state.settings
    try:
        with db.connect(settings.database_url) as conn:
            migration = _current_migration(conn)
    except psycopg.Error:
        logger.warning("health check: database query failed", exc_info=True)
        response.status_code = 503
        return Health(
            status="error", version=settings.git_sha, database="unreachable", migration=None
        )
    return Health(status="ok", version=settings.git_sha, database="ok", migration=migration)
