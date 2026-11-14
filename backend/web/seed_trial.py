"""Create a local-only trial account from the sanitized résumé profile seed."""
import argparse
import json
import os
from pathlib import Path
import secrets

from .storage import Store


FIXTURE = Path(__file__).with_name("fixtures") / "dhruva_trial_profile.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="dhruva-trial@orbit.local")
    args = parser.parse_args()
    data_dir = Path(os.getenv("WEB_DATA_DIR", ".web-data"))
    store = Store(data_dir / "app.sqlite3")
    password = secrets.token_urlsafe(18)
    try:
        user_id = store.create_user(args.email.strip().lower(), password)
    except ValueError as exc:
        parser.exit(1, f"{exc}. This local account is already seeded.\n")
    profile = json.loads(FIXTURE.read_text())
    store.update_profile(user_id, profile)
    credentials = data_dir / "local-trial-login.txt"
    credentials.write_text(f"URL: http://127.0.0.1:8010\nEmail: {args.email.strip().lower()}\nPassword: {password}\nSkill ratings are placeholder 1/5 from listed skills; edit them before interpreting matches.\n")
    credentials.chmod(0o600)
    print(f"Seeded the sanitized profile and {len(profile['projects'])} projects. Login details: {credentials}")


if __name__ == "__main__":
    main()
