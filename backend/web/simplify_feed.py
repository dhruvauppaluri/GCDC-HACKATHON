"""Read-only, four-hour cache of SimplifyJobs' public internship listings."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
from threading import Lock
import time

import httpx

from .jobs import SKILL_OPTIONS
from .job_descriptions import DESCRIPTION_TTL, JobDescriptionStore, enrich_listing


SOURCE_REPO = "https://github.com/SimplifyJobs/Summer2027-Internships"
SOURCE_JSON = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"
REFRESH_SECONDS = 4 * 60 * 60
CATEGORY_TRACK = {
    "Software": "software", "Software Engineering": "software", "AI/ML/Data": "software",
    "Data Science, AI & Machine Learning": "software", "Hardware": "hardware",
    "Product": "product", "Product Management": "product",
}
TRACK_LABEL = {"hardware": "HW", "software": "CS", "product": "PM"}


def normalize(raw: list, checked_at: str) -> list[dict]:
    jobs = []
    seen = set()
    for item in raw:
        if not isinstance(item, dict) or not item.get("active") or not item.get("is_visible"):
            continue
        track = CATEGORY_TRACK.get(item.get("category"))
        if not track or not any("2027" in str(term) for term in (item.get("terms") or [])):
            continue
        title, company, url, key = (item.get(field) for field in ("title", "company_name", "url", "id"))
        if not all(isinstance(value, str) and value.strip() for value in (title, company, url, key)) or not url.startswith("https://") or key in seen:
            continue
        seen.add(key)
        title_signals = [skill for skill in SKILL_OPTIONS[TRACK_LABEL[track]]
                         if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", title, re.I)]
        jobs.append({
            "job_id": f"simplify:{key}", "track": track, "title": title[:120], "company": company[:120],
            "description": "", "description_status": "listing_only", "required_skills": [], "preferred_skills": [],
            "title_signals": title_signals, "source": "simplify", "source_url": url,
            "source_repository": SOURCE_REPO, "retrieved_at": checked_at,
            "locations": (item.get("locations") or [])[:5], "terms": (item.get("terms") or [])[:5],
            "date_posted": item.get("date_posted") or 0, "date_updated": item.get("date_updated") or 0,
        })
    return jobs


class SimplifyFeed:
    def __init__(self, path: Path):
        self.path = path
        self.lock = Lock()
        self.descriptions = JobDescriptionStore(path.with_name("simplify-descriptions.sqlite3"))
        self.cache = {"checked_at": 0, "etag": None, "jobs": [], "error": None}
        if path.exists():
            try:
                self.cache.update(json.loads(path.read_text()))
            except (OSError, ValueError):
                pass

    def get(self) -> tuple[list[dict], dict]:
        if os.getenv("SIMPLIFY_FEED_ENABLED", "1") == "0":
            return [], {"source": SOURCE_REPO, "enabled": False}
        with self.lock:
            if time.time() - self.cache["checked_at"] >= REFRESH_SECONDS:
                self._refresh()
            jobs = list(self.cache["jobs"])
            checked_at, error = self.cache["checked_at"], self.cache["error"]
        descriptions = self.descriptions.all()
        enriched = []
        ready = failed = 0
        for job in jobs:
            cached = descriptions.get(job["source_url"])
            if cached and cached.get("description_fetch_status") == "fetched":
                ready += 1
                enriched.append({**job, **{key: value for key, value in cached.items() if key != "checked_at"}})
            elif cached:
                failed += 1
                enriched.append({**job, "description_fetch_status": "failed", "research_note": cached.get("research_note")})
            else:
                enriched.append({**job, "description_fetch_status": "pending"})
        return enriched, {
            "source": SOURCE_REPO, "enabled": True, "checked_at": checked_at,
            "count": len(jobs), "error": error, "refresh_interval_hours": 4,
            "description_ready": ready, "description_failed": failed,
            "description_pending": len(jobs) - ready - failed,
        }

    def refresh_next_descriptions(self, limit: int = 4) -> int:
        """Gradually fill the four-hour JD cache; never block a match request."""
        if os.getenv("SIMPLIFY_FEED_ENABLED", "1") == "0":
            return 0
        with self.lock:
            jobs = list(self.cache["jobs"])
        cached = self.descriptions.all()
        now = time.time()
        due = [job for job in jobs if now - cached.get(job["source_url"], {}).get("checked_at", 0) >= DESCRIPTION_TTL]
        due.sort(key=lambda job: (job["source_url"] in cached, -int(job.get("date_posted") or 0),
                                  cached.get(job["source_url"], {}).get("checked_at", 0)))
        selected = []
        seen_urls = set()
        for job in due:
            if job["source_url"] not in seen_urls:
                selected.append(job)
                seen_urls.add(job["source_url"])
            if len(selected) >= limit:
                break
        if not selected:
            return 0
        with ThreadPoolExecutor(max_workers=min(len(selected), 4), thread_name_prefix="job-description") as pool:
            for job, result in zip(selected, pool.map(enrich_listing, selected)):
                self.descriptions.put(job["source_url"], result)
        return len(selected)

    def enrich_now(self, job: dict) -> dict:
        if job.get("description_status") == "fetched":
            return job
        result = enrich_listing(job)
        self.descriptions.put(job["source_url"], result)
        return result

    def _refresh(self):
        headers = {"User-Agent": "SC-HACK-local-trial", "Accept": "application/json"}
        if self.cache.get("etag"):
            headers["If-None-Match"] = self.cache["etag"]
        try:
            response = httpx.get(SOURCE_JSON, headers=headers, timeout=30, follow_redirects=False)
            if response.status_code != 304:
                response.raise_for_status()
                if len(response.content) > 20_000_000:
                    raise ValueError("Simplify listing file exceeds the local cache limit")
                data = response.json()
                if not isinstance(data, list):
                    raise ValueError("Simplify listing file is not an array")
                checked = datetime.now(timezone.utc).isoformat()
                self.cache["jobs"] = normalize(data, checked)
                self.cache["etag"] = response.headers.get("etag")
            self.cache["checked_at"] = time.time()
            self.cache["error"] = None
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(self.cache))
            temporary.replace(self.path)
        except (httpx.HTTPError, ValueError, OSError) as exc:
            self.cache["error"] = str(exc)
            self.cache["checked_at"] = time.time() - REFRESH_SECONDS + 300
