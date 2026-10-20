"""Configuration, read once from the environment at startup."""

import os
from dataclasses import dataclass
from pathlib import Path

# In the container the built React app lives here (see Dockerfile).
DEFAULT_WEB_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"


@dataclass(frozen=True)
class Settings:
    database_url: str
    git_sha: str
    web_dist: Path

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from environment variables.

        Raises:
            KeyError: If DATABASE_URL is missing — the API is useless without a database.
        """
        return cls(
            database_url=os.environ["DATABASE_URL"],
            git_sha=os.environ.get("GIT_SHA", "unknown"),
            web_dist=Path(os.environ.get("WEB_DIST", DEFAULT_WEB_DIST)),
        )
