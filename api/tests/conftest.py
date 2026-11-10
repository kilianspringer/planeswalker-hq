"""Shared test fixtures.

Tests run against a real Postgres. Each test gets its own freshly created database, so
tests cannot see each other's tables and every migration test starts from zero.

TEST_DATABASE_URL must point at a server where the user may create databases. Locally that
is the Postgres from compose.dev.yml; in CI it is the service container.
"""

import os
import uuid
from collections.abc import Iterator

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

ADMIN_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/postgres"
)


@pytest.fixture
def database_url() -> Iterator[str]:
    """Create an empty throwaway database and return its connection URL."""
    name = f"test_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    try:
        yield make_conninfo(ADMIN_URL, dbname=name)
    finally:
        with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
def conn(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url, autocommit=True) as connection:
        yield connection
