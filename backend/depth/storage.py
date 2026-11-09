"""Small local SQLite job store. One worker process is intended for the demo."""
import json
import sqlite3
from pathlib import Path
from threading import Lock
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL, result TEXT, error TEXT, updated_at TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path)

    def put(self, job_id: str, payload: dict):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?)", (job_id, "queued", json.dumps(payload), None, None, now()))

    def get(self, job_id: str):
        with self.connect() as db:
            row = db.execute("SELECT status,payload,result,error,updated_at FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        return {"evaluation_id": job_id, "status": row[0], "payload": json.loads(row[1]), "result": json.loads(row[2]) if row[2] else None, "error": row[3], "updated_at": row[4]}

    def set(self, job_id: str, status: str, result=None, error=None):
        with self.lock, self.connect() as db:
            db.execute("UPDATE jobs SET status=?,result=?,error=?,updated_at=? WHERE id=?", (status, json.dumps(result) if result is not None else None, error, now(), job_id))

    def update_payload(self, job_id: str, payload: dict):
        with self.lock, self.connect() as db:
            db.execute("UPDATE jobs SET payload=?,updated_at=? WHERE id=?", (json.dumps(payload), now(), job_id))

    def unfinished(self):
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT id FROM jobs WHERE status IN ('queued','running')")]
