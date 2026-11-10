"""Create one local demo account; safe to run more than once."""
import os
from pathlib import Path

from backend.web.storage import Store


def main():
    store = Store(Path(os.getenv("WEB_DATA_DIR", ".web-data")) / "app.sqlite3")
    email = "demo@orbit.local"
    password = "DemoPass123!"
    try:
        user_id = store.create_user(email, password)
    except ValueError:
        print("Demo account already exists. Existing password was not changed.")
        return
    store.update_profile(user_id, {
        "first_name": "Alex", "last_name": "Rivera", "resume_name": "alex-resume.txt",
        "resume_text": "Built an FPGA image processing prototype in SystemVerilog, tested with Python, and developed a React portfolio.",
        "interests": "FPGA design, embedded systems, and useful software tools",
        "target_tracks": ["HW", "CS"],
        "skills": {"HW": {"FPGA": 4, "SystemVerilog": 3, "Python": 4}, "CS": {"React": 3, "Python": 4}},
        "completed": True,
    })
    print(f"Demo account: {email} / {password}")


if __name__ == "__main__":
    main()
