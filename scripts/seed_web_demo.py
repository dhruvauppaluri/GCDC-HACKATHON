"""Create synthetic local demo accounts from JSON fixtures; safe to repeat."""
import json
import os
from pathlib import Path

from backend.web.storage import Store

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "web" / "fixtures" / "users"
PASSWORD = "DemoPass123!"


def main():
    store = Store(Path(os.getenv("WEB_DATA_DIR", ".web-data")) / "app.sqlite3")
    created = skipped = 0
    for path in sorted(FIXTURES.glob("*.json")):
        fixture = json.loads(path.read_text())
        email, profile = fixture["email"], fixture["profile"]
        try:
            user_id = store.create_user(email, PASSWORD)
        except ValueError:
            skipped += 1
            continue
        store.update_profile(user_id, profile)
        created += 1
    print(f"Sample accounts: {created} created, {skipped} already present. Password: {PASSWORD}")
    print(f"Emails and scenarios: {FIXTURES}")


if __name__ == "__main__":
    main()
