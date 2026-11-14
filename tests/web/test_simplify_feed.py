from backend.web.jobs import match_jobs
from backend.web.simplify_feed import normalize


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
