"""Forward-only migration runner.

Reads db/migrations/NNNN_name.sql in version order and applies every file that has not run
yet. Three rules make this safe:

1. Each migration runs in its own transaction, together with the row that records it in
   schema_migrations. Either the whole file takes effect and is recorded, or nothing does.
2. The SHA-256 checksum of every applied file is stored. If an applied file is changed or
   removed later, the runner stops before touching anything: the database would otherwise
   silently differ from what the files describe.
3. Only forward. A new file must have a higher number than every applied one. To undo
   something, write a new migration.

Because the runner wraps each file in a transaction, a migration must not contain its own
BEGIN/COMMIT, nor statements that refuse to run in a transaction (CREATE INDEX CONCURRENTLY).

Usage: DATABASE_URL=postgresql://... python db/migrate.py
"""

import hashlib
import logging
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

logger = logging.getLogger("migrate")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
FILE_NAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")

# Arbitrary but fixed key for a Postgres advisory lock. While one runner holds it, a second
# runner (say, two deploys at once) waits instead of applying the same migration twice.
LOCK_KEY = 7_211_301


class MigrationError(Exception):
    """The migrations cannot be applied as they are."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str
    checksum: str

    @property
    def filename(self) -> str:
        return f"{self.version:04d}_{self.name}.sql"


def load_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Read all migration files, sorted by version.

    Raises:
        MigrationError: If a file name does not match NNNN_name.sql or a version repeats.
    """
    migrations: dict[int, Migration] = {}
    for path in sorted(directory.glob("*.sql")):
        match = FILE_NAME.match(path.name)
        if match is None:
            raise MigrationError(f"{path.name}: file name must look like 0001_lower_case.sql")
        version = int(match.group(1))
        if version in migrations:
            raise MigrationError(
                f"version {version} appears twice: {migrations[version].filename} and {path.name}"
            )
        content = path.read_bytes()
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise MigrationError(f"{path.name} is not valid UTF-8") from error
        migrations[version] = Migration(
            version=version,
            name=match.group(2),
            sql=text,
            checksum=hashlib.sha256(content).hexdigest(),
        )
    return [migrations[v] for v in sorted(migrations)]


def _applied(conn: psycopg.Connection) -> dict[int, tuple[str, str]]:
    """Return {version: (name, checksum)} of applied migrations; empty on a new database."""
    exists = conn.execute("SELECT to_regclass('schema_migrations') IS NOT NULL").fetchone()[0]
    if not exists:
        return {}
    rows = conn.execute("SELECT version, name, checksum FROM schema_migrations").fetchall()
    return {version: (name, checksum) for version, name, checksum in rows}


def _check(files: list[Migration], applied: dict[int, tuple[str, str]]) -> list[Migration]:
    """Compare files with the database and return the migrations still to run.

    Raises:
        MigrationError: If the files and the database disagree.
    """
    by_version = {m.version: m for m in files}
    for version, (name, checksum) in sorted(applied.items()):
        filename = f"{version:04d}_{name}.sql"
        current = by_version.get(version)
        if current is None or current.name != name:
            raise MigrationError(f"{filename} was applied but its file is missing")
        if current.checksum != checksum:
            raise MigrationError(
                f"{filename} was changed after it was applied. Restore the original file "
                "and put the change into a new migration."
            )

    pending = [m for m in files if m.version not in applied]
    newest_applied = max(applied, default=0)
    for migration in pending:
        if migration.version < newest_applied:
            raise MigrationError(
                f"{migration.filename} is older than the newest applied migration "
                f"({newest_applied:04d}). Give it a higher number."
            )
    return pending


def migrate(conn: psycopg.Connection, directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Apply all pending migrations and return the ones that ran.

    The connection must be in autocommit mode, so that every migration gets a transaction
    of its own.

    Raises:
        MigrationError: If the files and the database disagree or a migration fails. A
            failed migration leaves no trace; earlier ones in the same run stay applied.
    """
    if not conn.autocommit:
        raise MigrationError("the connection must be in autocommit mode")

    files = load_migrations(directory)
    conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
    try:
        # Read the state only after taking the lock: another runner may just have finished.
        pending = _check(files, _applied(conn))
        for migration in pending:
            _apply(conn, migration)
        return pending
    finally:
        # If the connection broke, Postgres has released the lock with the session already;
        # a failing unlock must not hide the error that got us here.
        if not conn.closed:
            try:
                conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))
            except psycopg.Error:
                logger.warning("could not release the advisory lock", exc_info=True)


def _apply(conn: psycopg.Connection, migration: Migration) -> None:
    try:
        with conn.transaction():
            # No parameters: psycopg sends the file as is, several statements at once.
            conn.execute(migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
    except psycopg.Error as error:
        raise MigrationError(f"{migration.filename} failed and was rolled back: {error}") from error
    logger.info("applied %s", migration.filename)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL is not set")
        return 2
    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            applied = migrate(conn)
    except MigrationError as error:
        logger.error("%s", error)
        return 1
    if not applied:
        logger.info("database is up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
