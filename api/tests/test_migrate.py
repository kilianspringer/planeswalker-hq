"""Tests for the forward-only migration runner in db/migrate.py."""

import threading
from pathlib import Path

import psycopg
import pytest

import migrate

INIT_SQL = (migrate.MIGRATIONS_DIR / "0001_init.sql").read_text()


def write(directory: Path, filename: str, content: str) -> None:
    (directory / filename).write_text(content)


def table_exists(conn: psycopg.Connection, name: str) -> bool:
    return conn.execute("SELECT to_regclass(%s) IS NOT NULL", (name,)).fetchone()[0]


def applied_versions(conn: psycopg.Connection) -> list[int]:
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [row[0] for row in rows]


@pytest.fixture
def migrations(tmp_path: Path) -> Path:
    """A migrations directory that starts with the real 0001_init.sql."""
    write(tmp_path, "0001_init.sql", INIT_SQL)
    return tmp_path


def test_new_migrations_run_in_order(conn, migrations):
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")

    applied = migrate.migrate(conn, migrations)

    assert [m.version for m in applied] == [1, 2]
    assert applied_versions(conn) == [1, 2]
    assert table_exists(conn, "widget")


def test_applied_migrations_are_skipped(conn, migrations):
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")
    migrate.migrate(conn, migrations)

    # A second run must not execute anything again; CREATE TABLE would fail if it did.
    assert migrate.migrate(conn, migrations) == []
    assert applied_versions(conn) == [1, 2]


def test_only_the_new_migration_runs(conn, migrations):
    migrate.migrate(conn, migrations)
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")

    applied = migrate.migrate(conn, migrations)

    assert [m.version for m in applied] == [2]


def test_changed_migration_aborts(conn, migrations):
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")
    migrate.migrate(conn, migrations)

    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id bigint PRIMARY KEY);")
    write(migrations, "0003_gadget.sql", "CREATE TABLE gadget (id integer PRIMARY KEY);")

    with pytest.raises(migrate.MigrationError, match="0002_widget.sql.*changed"):
        migrate.migrate(conn, migrations)
    # The check happens before anything runs: 0003 must not have been applied.
    assert not table_exists(conn, "gadget")
    assert applied_versions(conn) == [1, 2]


def test_failing_migration_leaves_nothing_behind(conn, migrations):
    migrate.migrate(conn, migrations)
    write(
        migrations,
        "0002_broken.sql",
        "CREATE TABLE half_done (id integer PRIMARY KEY);\nSELECT * FROM no_such_table;",
    )

    with pytest.raises(migrate.MigrationError, match="0002_broken.sql"):
        migrate.migrate(conn, migrations)

    # The whole file ran in one transaction, so its first statement was rolled back too,
    # and the migration was not recorded.
    assert not table_exists(conn, "half_done")
    assert applied_versions(conn) == [1]


def test_failing_migration_stops_later_ones(conn, migrations):
    write(migrations, "0002_broken.sql", "SELECT * FROM no_such_table;")
    write(migrations, "0003_gadget.sql", "CREATE TABLE gadget (id integer PRIMARY KEY);")

    with pytest.raises(migrate.MigrationError):
        migrate.migrate(conn, migrations)

    assert applied_versions(conn) == [1]
    assert not table_exists(conn, "gadget")


def test_missing_applied_migration_aborts(conn, migrations):
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")
    migrate.migrate(conn, migrations)
    (migrations / "0002_widget.sql").unlink()

    with pytest.raises(migrate.MigrationError, match="0002_widget.sql.*missing"):
        migrate.migrate(conn, migrations)


def test_out_of_order_migration_aborts(conn, migrations):
    write(migrations, "0003_gadget.sql", "CREATE TABLE gadget (id integer PRIMARY KEY);")
    migrate.migrate(conn, migrations)
    # Someone adds a migration with a lower number than one that already ran.
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")

    with pytest.raises(migrate.MigrationError, match="0002_widget.sql.*older"):
        migrate.migrate(conn, migrations)
    assert not table_exists(conn, "widget")


@pytest.mark.parametrize(
    "filename",
    ["2_widget.sql", "0002-widget.sql", "0002_Widget.sql", "0002_widget.txt.sql"],
)
def test_badly_named_file_aborts(migrations, filename):
    write(migrations, filename, "SELECT 1;")

    with pytest.raises(migrate.MigrationError, match="file name"):
        migrate.load_migrations(migrations)


def test_duplicate_version_aborts(migrations):
    write(migrations, "0002_widget.sql", "SELECT 1;")
    write(migrations, "0002_gadget.sql", "SELECT 1;")

    with pytest.raises(migrate.MigrationError, match="version 2"):
        migrate.load_migrations(migrations)


def test_checksum_is_recorded(conn, migrations):
    migrate.migrate(conn, migrations)

    name, checksum = conn.execute(
        "SELECT name, checksum FROM schema_migrations WHERE version = 1"
    ).fetchone()
    assert name == "init"
    assert checksum == migrate.load_migrations(migrations)[0].checksum
    assert len(checksum) == 64


def test_real_migrations_apply_cleanly(conn):
    applied = migrate.migrate(conn)

    assert applied, "db/migrations must contain at least 0001_init.sql"
    assert applied_versions(conn) == [m.version for m in applied]


def test_runner_refuses_a_connection_outside_autocommit(database_url, migrations):
    with psycopg.connect(database_url) as conn:
        with pytest.raises(migrate.MigrationError, match="autocommit"):
            migrate.migrate(conn, migrations)


def test_second_runner_waits_for_the_lock(database_url, conn, migrations):
    write(migrations, "0002_widget.sql", "CREATE TABLE widget (id integer PRIMARY KEY);")
    # Another runner holds the lock, as during a concurrent deploy.
    conn.execute("SELECT pg_advisory_lock(%s)", (migrate.LOCK_KEY,))
    result: list[list[migrate.Migration]] = []

    def run() -> None:
        with psycopg.connect(database_url, autocommit=True) as other:
            result.append(migrate.migrate(other, migrations))

    runner = threading.Thread(target=run)
    runner.start()
    runner.join(timeout=1)
    assert runner.is_alive(), "runner must wait while the lock is held"
    assert not table_exists(conn, "widget")

    conn.execute("SELECT pg_advisory_unlock(%s)", (migrate.LOCK_KEY,))
    runner.join(timeout=10)

    assert not runner.is_alive()
    assert [m.version for m in result[0]] == [1, 2]


def test_non_utf8_file_aborts(migrations):
    (migrations / "0002_latin1.sql").write_bytes("-- L\xf3rien".encode("latin-1"))

    with pytest.raises(migrate.MigrationError, match="UTF-8"):
        migrate.load_migrations(migrations)


def test_main_without_database_url_exits_2(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert migrate.main() == 2


def test_main_applies_and_reports(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)

    assert migrate.main() == 0
    assert migrate.main() == 0
