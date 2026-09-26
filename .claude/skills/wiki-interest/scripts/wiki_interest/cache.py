"""SQLite cache for pageviews and API lookups.

Daily pageviews for completed days never change, so they are kept forever.
`coverage` records which day range was fetched for each (project, title), so a
follow-up query only downloads the days it is missing.
"""

import json
import os
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]


def home() -> Path:
    path = Path(os.environ.get("WIKI_INTEREST_HOME", SKILL_DIR))
    path.mkdir(parents=True, exist_ok=True)
    return path


class Cache:
    def __init__(self, path: Path | None = None):
        path = path or home() / ".cache" / "cache.sqlite"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=10)
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS pageviews (
                project TEXT, title TEXT, day TEXT, views INTEGER,
                PRIMARY KEY (project, title, day));
            CREATE TABLE IF NOT EXISTS coverage (
                project TEXT, title TEXT, start TEXT, end TEXT,
                PRIMARY KEY (project, title));
            CREATE TABLE IF NOT EXISTS lookups (
                key TEXT PRIMARY KEY, value TEXT, fetched_at REAL);
            """
        )

    def __del__(self):
        if self.db:
            self.db.close()

    def coverage(self, project: str, title: str) -> tuple[date, date] | None:
        row = self.db.execute(
            "SELECT start, end FROM coverage WHERE project=? AND title=?", (project, title)
        ).fetchone()
        return (date.fromisoformat(row[0]), date.fromisoformat(row[1])) if row else None

    def missing_ranges(self, project: str, title: str, start: date, end: date) -> list[tuple[date, date]]:
        """Day ranges inside [start, end] that are not cached yet."""
        cov = self.coverage(project, title)
        if cov is None or cov[1] < start - timedelta(days=1) or cov[0] > end + timedelta(days=1):
            return [(start, end)]
        ranges = []
        if start < cov[0]:
            ranges.append((start, cov[0] - timedelta(days=1)))
        if end > cov[1]:
            ranges.append((cov[1] + timedelta(days=1), end))
        return ranges

    def store(self, project: str, title: str, start: date, end: date, views: dict[date, int]) -> None:
        """Store daily views for [start, end]; days absent from `views` are zero."""
        self.db.executemany(
            "INSERT OR REPLACE INTO pageviews VALUES (?, ?, ?, ?)",
            [(project, title, d.isoformat(), v) for d, v in views.items()],
        )
        cov = self.coverage(project, title)
        new_start, new_end = (min(start, cov[0]), max(end, cov[1])) if cov else (start, end)
        self.db.execute(
            "INSERT OR REPLACE INTO coverage VALUES (?, ?, ?, ?)",
            (project, title, new_start.isoformat(), new_end.isoformat()),
        )
        self.db.commit()

    def daily(self, project: str, title: str, start: date, end: date) -> dict[date, int]:
        rows = self.db.execute(
            "SELECT day, views FROM pageviews WHERE project=? AND title=? AND day BETWEEN ? AND ?",
            (project, title, start.isoformat(), end.isoformat()),
        )
        return {date.fromisoformat(d): v for d, v in rows}

    def get_lookup(self, key: str, max_age_days: float = 30):
        row = self.db.execute("SELECT value, fetched_at FROM lookups WHERE key=?", (key,)).fetchone()
        if row and time.time() - row[1] < max_age_days * 86400:
            return json.loads(row[0])
        return None

    def put_lookup(self, key: str, value) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO lookups VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), time.time()),
        )
        self.db.commit()
