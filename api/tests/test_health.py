"""Tests for GET /health."""

import psycopg
import pytest
from fastapi.testclient import TestClient

import migrate
from app.main import create_app
from app.settings import Settings


def client_for(database_url: str, tmp_path, git_sha: str = "a" * 40) -> TestClient:
    settings = Settings(database_url=database_url, git_sha=git_sha, web_dist=tmp_path)
    return TestClient(create_app(settings))


@pytest.fixture
def migrated_url(database_url: str) -> str:
    with psycopg.connect(database_url, autocommit=True) as conn:
        migrate.migrate(conn)
    return database_url


def test_health_reports_version_and_migration(migrated_url, tmp_path):
    newest = migrate.load_migrations()[-1]

    with client_for(migrated_url, tmp_path, git_sha="b" * 40) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "b" * 40,
        "database": "ok",
        "migration": {"version": newest.version, "name": newest.name},
    }


def test_health_without_migrations_reports_none(database_url, tmp_path):
    with client_for(database_url, tmp_path) as client:
        body = client.get("/health").json()

    assert body["database"] == "ok"
    assert body["migration"] is None


def test_health_with_unreachable_database_returns_503(tmp_path):
    # Port 1 is never a Postgres server; the connection is refused at once.
    url = "postgresql://nobody:nothing@127.0.0.1:1/none?connect_timeout=1"

    with client_for(url, tmp_path) as client:
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["database"] == "unreachable"
    assert body["version"] == "a" * 40


def test_built_frontend_is_served_at_root(database_url, tmp_path):
    (tmp_path / "index.html").write_text("<title>Planeswalker HQ</title>")

    with client_for(database_url, tmp_path) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Planeswalker HQ" in response.text


def test_api_runs_without_built_frontend(database_url, tmp_path):
    missing = tmp_path / "no-dist"

    with client_for(database_url, missing) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 404
