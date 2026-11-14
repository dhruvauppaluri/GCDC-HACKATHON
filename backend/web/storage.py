"""SQLite-backed accounts, profiles, and server-side sessions."""
import json
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from hashlib import scrypt, sha256
from pathlib import Path
from threading import Lock


def utcnow():
    return datetime.now(timezone.utc)


def default_profile():
    return {
        "first_name": "", "last_name": "", "resume_name": "", "resume_text": "",
        "interests": "", "target_tracks": [], "skills": {}, "linkedin_url": "",
        "github_url": "", "website_url": "", "projects": [], "completed": False,
    }


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = Lock()
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, profile TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL, expires_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
            db.execute("CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
            db.execute("CREATE TABLE IF NOT EXISTS pasted_jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")
            db.execute("CREATE TABLE IF NOT EXISTS reviews (case_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT, error TEXT, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id))")

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _hash(password: str, salt: bytes):
        return scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1).hex()

    def create_user(self, email: str, password: str):
        user_id = secrets.token_urlsafe(18)
        salt = os.urandom(16)
        with self.lock, self.connect() as db:
            try:
                db.execute("INSERT INTO users VALUES (?,?,?,?,?)", (user_id, email, salt.hex(), self._hash(password, salt), json.dumps(default_profile())))
            except sqlite3.IntegrityError as exc:
                raise ValueError("An account with that email already exists") from exc
        return user_id

    def authenticate(self, email: str, password: str):
        with self.connect() as db:
            row = db.execute("SELECT id,salt,password_hash FROM users WHERE email=?", (email,)).fetchone()
        if not row:
            self._hash(password, bytes(16))
            return None
        expected = self._hash(password, bytes.fromhex(row["salt"]))
        return row["id"] if secrets.compare_digest(expected, row["password_hash"]) else None

    def new_session(self, user_id: str):
        token = secrets.token_urlsafe(32)
        expires = (utcnow() + timedelta(days=30)).isoformat()
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?)", (sha256(token.encode()).hexdigest(), user_id, expires))
        return token

    def user_for_session(self, token: str | None):
        if not token:
            return None
        with self.connect() as db:
            row = db.execute("SELECT u.id,u.email,u.profile,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=?", (sha256(token.encode()).hexdigest(),)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= utcnow():
            return None
        return {"id": row["id"], "email": row["email"], "profile": json.loads(row["profile"])}

    def get_user(self, user_id: str):
        with self.connect() as db:
            row = db.execute("SELECT id,email,profile FROM users WHERE id=?", (user_id,)).fetchone()
        return {"id": row["id"], "email": row["email"], "profile": json.loads(row["profile"])} if row else None

    def delete_session(self, token: str | None):
        if token:
            with self.lock, self.connect() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (sha256(token.encode()).hexdigest(),))

    def update_profile(self, user_id: str, changes: dict):
        with self.lock, self.connect() as db:
            row = db.execute("SELECT profile FROM users WHERE id=?", (user_id,)).fetchone()
            profile = json.loads(row["profile"])
            profile.update(changes)
            db.execute("UPDATE users SET profile=? WHERE id=?", (json.dumps(profile), user_id))
        return profile

    def put_case(self, case_id: str, user_id: str, payload: dict):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO cases VALUES (?,?,?,?)", (case_id, user_id, json.dumps(payload), utcnow().isoformat()))

    def get_case(self, case_id: str, user_id: str):
        with self.connect() as db:
            row = db.execute("SELECT payload,created_at FROM cases WHERE id=? AND user_id=?", (case_id, user_id)).fetchone()
        return {**json.loads(row["payload"]), "created_at": row["created_at"]} if row else None

    def put_pasted_job(self, user_id: str, job: dict):
        with self.lock, self.connect() as db:
            db.execute("INSERT INTO pasted_jobs VALUES (?,?,?,?)", (job["job_id"], user_id, json.dumps(job), utcnow().isoformat()))

    def pasted_jobs(self, user_id: str):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM pasted_jobs WHERE user_id=? ORDER BY created_at DESC", (user_id,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def put_review(self, case_id: str, user_id: str):
        with self.lock, self.connect() as db:
            db.execute("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?)", (case_id, user_id, "pending", None, None, utcnow().isoformat()))

    def finish_review(self, case_id: str, result: dict | None = None, error: str | None = None):
        with self.lock, self.connect() as db:
            db.execute("UPDATE reviews SET status=?, payload=?, error=? WHERE case_id=?", ("failed" if error else "complete", json.dumps(result) if result else None, error, case_id))

    def get_review(self, case_id: str, user_id: str):
        with self.connect() as db:
            row = db.execute("SELECT status,payload,error FROM reviews WHERE case_id=? AND user_id=?", (case_id, user_id)).fetchone()
        return {"status": row["status"], "result": json.loads(row["payload"]) if row["payload"] else None, "error": row["error"]} if row else None
