"""Read-only, four-hour cache of SimplifyJobs' public internship listings."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from threading import Lock
import time

import httpx

from .jobs import SKILL_OPTIONS
from .imports import TextExtractor, validate_public_url
from .jobs import parse_job_description


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
            return list(self.cache["jobs"]), {
                "source": SOURCE_REPO, "enabled": True, "checked_at": self.cache["checked_at"],
                "count": len(self.cache["jobs"]), "error": self.cache["error"],
                "refresh_interval_hours": 4,
            }

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


def enrich_listing(job: dict) -> dict:
    """Fetch the original posting on interest; preserve a listing-only fallback."""
    enriched = dict(job)
    try:
        validate_public_url(job["source_url"])
        with httpx.Client(timeout=12, follow_redirects=False) as client:
            with client.stream("GET", job["source_url"], headers={"User-Agent": "SC-HACK-local-trial"}) as response:
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", ""):
                    raise ValueError("Original posting did not return HTML")
                chunks, length = [], 0
                for chunk in response.iter_bytes():
                    length += len(chunk)
                    if length > 200_000:
                        break
                    chunks.append(chunk)
        parser = TextExtractor()
        parser.feed(b"".join(chunks).decode("utf-8", errors="replace"))
        text = "\n".join(parser.parts)[:20_000]
        if len(text) < 100:
            raise ValueError("Original posting has too little readable text")
        parsed = parse_job_description(text, job["track"], job["title"], job["company"])
        enriched.update(description=text, description_status="fetched", required_skills=parsed["required_skills"],
                        preferred_skills=parsed["preferred_skills"], research_note="Requirements were extracted from the linked posting; review them against the original.")
    except (ValueError, httpx.HTTPError, KeyError) as exc:
        enriched.update(description=f"Listing for {job['title']} at {job['company']}. Full job description unavailable.",
                        description_status="listing_only", research_note=f"Could not read the original posting: {exc}. Paste the full JD for a stronger review.")
    return enriched
