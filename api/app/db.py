"""Database access: connections and the hand-written SQL in app/queries/."""

from functools import cache
from pathlib import Path

import psycopg

QUERIES_DIR = Path(__file__).resolve().parent / "queries"


def connect(database_url: str) -> psycopg.Connection:
    """Open a connection; give up after a few seconds instead of hanging a request."""
    return psycopg.connect(database_url, connect_timeout=3)


@cache
def query(name: str) -> str:
    """Return the SQL text of app/queries/<name>.sql."""
    return (QUERIES_DIR / f"{name}.sql").read_text()
