from backend.web.jobs import match_jobs
import json
import time

from backend.web.job_descriptions import extract_description
from backend.web.simplify_feed import SimplifyFeed, normalize


def test_simplify_feed_filters_and_screens_listing_titles():
    rows = [
        {"id": "one", "active": True, "is_visible": True, "category": "Hardware", "title": "FPGA Design Intern", "company_name": "Demo", "url": "https://example.com/job", "terms": ["Summer 2027"], "locations": ["Remote"], "date_posted": 123},
        {"id": "two", "active": False, "is_visible": True, "category": "Hardware", "title": "FPGA Intern", "company_name": "Closed", "url": "https://example.com/closed", "terms": ["Summer 2027"]},
        {"id": "three", "active": True, "is_visible": True, "category": "Quant", "title": "Quant Intern", "company_name": "Other", "url": "https://example.com/quant", "terms": ["Summer 2027"]},
    ]
    jobs = normalize(rows, "2026-11-13T00:00:00Z")
    assert len(jobs) == 1
    assert jobs[0]["title_signals"] == ["FPGA"]
    profile = {"target_tracks": ["HW"], "skills": {"HW": {"FPGA": 3}}, "projects": []}
    screen = match_jobs(profile, jobs)[0]
    assert screen["screening"]["verdict"] == "worth_exploring"
    assert screen["required_skills"] == []
    assert "full requirements are not available" in screen["screening"]["advocate"][0]


def test_extracts_structured_job_description_not_page_title():
    description = "Software engineering intern. Responsibilities include designing Python APIs and testing services. Requirements include Python and SQL experience."
    html = f'<script type="application/ld+json; charset=utf-8">{json.dumps({"@type": "JobPosting", "description": description})}</script>'
    text, source = extract_description(html, "Software Engineering Intern")
    assert text == description
    assert source == "jobposting_jsonld"


def test_rejects_listing_page_without_full_description():
    try:
        extract_description("<h1>Software Engineering Intern</h1><p>Apply now</p>", "Software Engineering Intern")
    except ValueError as exc:
        assert "reliable job description" in str(exc)
    else:
        raise AssertionError("Listing title was mistaken for a full description")


def test_unreadable_link_never_becomes_a_job_description(monkeypatch):
    from backend.web import job_descriptions

    monkeypatch.setattr(job_descriptions, "_read_html", lambda url: "<h1>Software Engineering Intern</h1>")
    result = job_descriptions.enrich_listing({
        "source_url": "https://example.com/job", "title": "Software Engineering Intern",
        "track": "software", "company": "Demo", "description": "",
    })
    assert result["description"] == ""
    assert result["description_status"] == "listing_only"
    assert result["description_fetch_status"] == "failed"
    assert result["required_skills"] == []


def test_background_description_cache_changes_quick_match(tmp_path, monkeypatch):
    from backend.web import simplify_feed

    monkeypatch.setenv("SIMPLIFY_FEED_ENABLED", "1")
    feed = SimplifyFeed(tmp_path / "feed.json")
    feed.cache = {"checked_at": time.time(), "jobs": normalize([{
        "id": "one", "active": True, "is_visible": True, "category": "Software",
        "title": "Software Engineering Intern", "company_name": "Demo",
        "url": "https://example.com/job", "terms": ["Summer 2027"], "date_posted": 123,
    }], "2026-11-13T00:00:00Z"), "etag": None, "error": None}
    monkeypatch.setattr(simplify_feed, "enrich_listing", lambda job: {
        **job, "description": "Build Python APIs and SQL data services for a growing platform.",
        "description_status": "fetched", "description_fetch_status": "fetched",
        "description_source": "jobposting_jsonld", "required_skills": ["Python", "SQL"],
        "preferred_skills": [], "research_note": "Extracted from linked posting.",
    })
    profile = {"target_tracks": ["CS"], "skills": {"CS": {"Python": 3}}, "projects": []}
    before = match_jobs(profile, feed.get()[0])[0]
    assert before["matched_skills"] == []
    assert feed.refresh_next_descriptions() == 1
    jobs, status = feed.get()
    after = match_jobs(profile, jobs)[0]
    assert status["description_ready"] == 1
    assert after["matched_skills"] == ["Python"]
    assert after["skill_gaps"] == []
    assert "qualification status is verified only" in after["screening"]["note"]
    assert feed.refresh_next_descriptions() == 0
