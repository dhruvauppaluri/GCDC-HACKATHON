"""Bounded extraction and local cache for linked employer job descriptions."""
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urljoin

import httpx

from .imports import TextExtractor, validate_public_url
from .jobs import parse_job_description


DESCRIPTION_TTL = 4 * 60 * 60
MAX_HTML_BYTES = 300_000
MAX_DESCRIPTION_CHARS = 12_000


class JobDescriptionStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS descriptions (
                url TEXT PRIMARY KEY, checked_at REAL NOT NULL, payload TEXT NOT NULL
            )""")

    def _connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def all(self) -> dict[str, dict]:
        with self._connect() as db:
            return {url: {"checked_at": checked_at, **json.loads(payload)}
                    for url, checked_at, payload in db.execute("SELECT url, checked_at, payload FROM descriptions")}

    def put(self, url: str, result: dict, checked_at: float | None = None):
        payload = {key: result.get(key) for key in (
            "description", "description_status", "description_fetch_status", "description_source",
            "required_skills", "preferred_skills", "research_note", "description_checked_at",
        )}
        with self._connect() as db:
            db.execute("INSERT OR REPLACE INTO descriptions (url, checked_at, payload) VALUES (?, ?, ?)",
                       (url, checked_at if checked_at is not None else time.time(), json.dumps(payload)))


class _JobPostingScripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.current = []
        self.scripts = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").casefold().split(";", 1)[0].strip() == "application/ld+json":
            self.active = True
            self.current = []

    def handle_data(self, data):
        if self.active:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.scripts.append("".join(self.current))
            self.active = False


def _posting(node):
    if isinstance(node, list):
        return next((found for item in node if (found := _posting(item))), None)
    if isinstance(node, dict):
        types = node.get("@type", [])
        types = [types] if isinstance(types, str) else types
        if any(str(kind).casefold().endswith("jobposting") for kind in types) and node.get("description"):
            return node
        return next((found for item in node.values() if (found := _posting(item))), None)
    return None


def extract_description(html: str, title: str) -> tuple[str, str]:
    """Prefer JobPosting structured data; accept plausible visible job content."""
    scripts = _JobPostingScripts()
    scripts.feed(html)
    for script in scripts.scripts:
        try:
            posting = _posting(json.loads(script))
        except (ValueError, TypeError):
            continue
        if posting:
            parser = TextExtractor()
            parser.feed(str(posting["description"]))
            text = "\n".join(parser.parts).strip()
            if len(text) >= 120:
                return text[:MAX_DESCRIPTION_CHARS], "jobposting_jsonld"
    parser = TextExtractor()
    parser.feed(html)
    text = "\n".join(parser.parts).strip()
    significant_title = [word for word in re.findall(r"[a-z0-9]+", title.casefold()) if len(word) >= 4]
    title_seen = sum(word in text.casefold() for word in significant_title[:4]) >= min(2, len(significant_title))
    job_sections = sum(term in text.casefold() for term in (
        "responsibilities", "qualifications", "requirements", "what you'll do", "what you will do", "about the role"))
    if len(text) >= 300 and title_seen and job_sections >= 2:
        return text[:MAX_DESCRIPTION_CHARS], "visible_job_page"
    raise ValueError("Linked page did not expose a reliable job description")


def _read_html(url: str) -> str:
    with httpx.Client(timeout=12, follow_redirects=False, headers={"User-Agent": "SC-HACK-local-trial"}) as client:
        for _ in range(4):
            validate_public_url(url)
            with client.stream("GET", url) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Linked page redirected without a destination")
                    url = urljoin(url, location)
                    continue
                response.raise_for_status()
                if "text/html" not in response.headers.get("content-type", "").casefold():
                    raise ValueError("Linked posting did not return HTML")
                chunks, total = [], 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_HTML_BYTES:
                        raise ValueError("Linked posting exceeded the page size limit")
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8", errors="replace")
    raise ValueError("Linked posting redirected too many times")


def enrich_listing(job: dict) -> dict:
    """Read the original posting without treating title metadata as a full JD."""
    enriched = dict(job)
    try:
        html = _read_html(job["source_url"])
        text, source = extract_description(html, job["title"])
        parsed = parse_job_description(text, job["track"], job["title"], job["company"])
        enriched.update(description=text, description_status="fetched", description_fetch_status="fetched",
                        description_source=source, required_skills=parsed["required_skills"],
                        preferred_skills=parsed["preferred_skills"],
                        research_note="Requirements were extracted from the linked posting; review them against the original.")
    except (ValueError, httpx.HTTPError, KeyError) as exc:
        enriched.update(description="", description_status="listing_only", description_fetch_status="failed",
                        description_source=None, required_skills=[], preferred_skills=[],
                        research_note=f"Could not verify a full description from the linked posting: {exc}.")
    enriched["description_checked_at"] = datetime.now(timezone.utc).isoformat()
    return enriched
