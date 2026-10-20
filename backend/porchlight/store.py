"""SQLite storage for events (what the dashboard shows) and observations (what the camera saw)."""
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from .vision import Observation


class Store:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.lock = threading.Lock()
        with self.lock, self.db:
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, time TEXT NOT NULL, type TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS events_time ON events(time);
                CREATE TABLE IF NOT EXISTS observations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT NOT NULL, source TEXT NOT NULL,
                    activity TEXT NOT NULL, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS observations_time ON observations(time);
                CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            """)

    # --- events -----------------------------------------------------------------------------------
    def add_event(self, event: dict) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO events VALUES (?, ?, ?, ?)",
                            (event["id"], event["time"], event["type"], json.dumps(event)))

    def events(self, since: str | None = None, until: str | None = None, limit: int = 500,
               source: str | None = None) -> list[dict]:
        q, args = "SELECT body FROM events WHERE 1=1", []
        if source:
            q, args = q + " AND json_extract(body, '$.source') = ?", args + [source]
        if since:
            q, args = q + " AND time >= ?", args + [since]
        if until:
            q, args = q + " AND time < ?", args + [until]
        q += " ORDER BY time DESC, rowid DESC LIMIT ?"
        with self.lock:
            rows = self.db.execute(q, args + [limit]).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]

    # --- observations -----------------------------------------------------------------------------
    def add_observation(self, obs: Observation) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT INTO observations (time, source, activity, body) VALUES (?, ?, ?, ?)",
                            (obs.time.isoformat(), obs.source, obs.activity, json.dumps(obs.to_json())))

    def observations(self, since: datetime, until: datetime | None = None,
                     activities: list[str] | None = None, source: str | None = None) -> list[Observation]:
        q, args = "SELECT body FROM observations WHERE time >= ?", [since.isoformat()]
        if source:
            q, args = q + " AND source = ?", args + [source]
        if until:
            q, args = q + " AND time < ?", args + [until.isoformat()]
        if activities:
            q += f" AND activity IN ({','.join('?' * len(activities))})"
            args += activities
        with self.lock:
            rows = self.db.execute(q + " ORDER BY time", args).fetchall()
        return [Observation.from_json(json.loads(r[0])) for r in rows]

    def clear_source(self, source: str) -> None:
        """Remove replayed data so a demo scenario can be run again from a clean slate."""
        with self.lock, self.db:
            self.db.execute("DELETE FROM observations WHERE source = ?", (source,))
            self.db.execute("DELETE FROM events WHERE json_extract(body, '$.source') = ?", (source,))

    # --- small key/value state --------------------------------------------------------------------
    def get(self, key: str, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, key: str, value) -> None:
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO kv VALUES (?, ?)", (key, json.dumps(value)))
