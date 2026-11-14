"""Local trial: pasted jobs, claim extraction, Depth citations, and the review handoff."""
from fastapi.testclient import TestClient
import pytest

from backend.web import api, cases, review
from data.fixtures.rishi import lawyers_grounded
from backend.web.jobs import parse_job_description, match_jobs
from backend.web.storage import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "store", Store(tmp_path / "trial.sqlite3"))
    return TestClient(api.app)


def test_parse_job_description_detects_track_and_allows_override():
    text = "FPGA design intern. Required: SystemVerilog and FPGA verification. Preferred: Python simulation experience."
    parsed = parse_job_description(text)
    assert parsed["track"] == "hardware"
    assert "SystemVerilog" in parsed["required_skills"]
    assert "Python" in parsed["preferred_skills"]
    assert parse_job_description(text, "product")["track"] == "product"


def test_job_sections_and_alternatives_are_not_hard_requirements():
    text = "Software engineering intern\nMinimum Qualifications:\nPython or Java\nPreferred Qualifications:\nSQL"
    parsed = parse_job_description(text)
    assert parsed["required_skills"] == ["Python or Java"]
    assert parsed["preferred_skills"] == ["SQL"]
    profile = {"target_tracks": ["CS"], "skills": {"CS": {"Java": 4}}, "projects": []}
    match = match_jobs(profile, [{**parsed, "job_id": "alternative", "source": "pasted"}])[0]
    assert match["matched_skills"] == ["Python or Java"]
    assert match["skill_gaps"] == []


def test_skill_in_job_overview_is_not_assumed_required():
    parsed = parse_job_description("Python software intern. Build internal tools for the engineering team. Preferred Qualifications:\nSQL")
    assert parsed["required_skills"] == []
    assert parsed["preferred_skills"] == ["SQL"]


def test_judge_needs_evidence_for_each_required_skill():
    inputs = {"job": {"required_skills": ["Java", "SQL"]}, "depth_projects": [{"dimensions": {"implementation": {"score": 2}}}],
              "evidence": [{"id": "depth:e:E1", "source": "depth_repository", "location": "route.java",
                            "excerpt": "Java shuttle planner"}]}
    positive = {category: [] for category in review.lawyers.CATEGORIES}
    negative = {category: [] for category in review.lawyers.CATEGORIES}
    positive["projects"] = [{"text": "Implemented a Java shuttle planner and SQL queries.",
                              "evidence_ids": ["depth:e:E1"], "kind": "artifact_evidence"}]
    result = review.trial_judge(inputs, positive, negative)
    assert result["verdict"] == "needs_more_evidence"
    assert result["required_skill_evidence"] == [
        {"requirement": "Java", "status": "artifact_supported", "evidence_ids": ["depth:e:E1"]},
        {"requirement": "SQL", "status": "unknown", "evidence_ids": []},
    ]


def test_website_review_verifies_claims_before_judging(monkeypatch):
    inputs = {"job": {"job_id": "j", "required_skills": ["SQL"]},
              "requirements": [{"id": "required:1", "kind": "required", "text": "SQL"}],
              "depth_projects": [{"dimensions": {"implementation": {"score": 2}}}],
              "evidence": [{"id": "depth:e:E1", "source": "depth_repository", "location": "route.java",
                            "excerpt": "Java shuttle planner"}]}
    calls = []
    def fake_lawyer(model, role, requirements, evidence, depth_projects, positive_review=None):
        result = {category: [] for category in review.lawyers.CATEGORIES}
        if role == "positive":
            result["projects"] = [{"text": "Demonstrated SQL", "evidence_ids": ["depth:e:E1"],
                                   "kind": "artifact_evidence"}]
        return result
    def fake_verify(payload):
        calls.append(payload)
        return {"0": False}
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    monkeypatch.setattr(lawyers_grounded, "chat", fake_verify)
    result = review.run_review(inputs)
    assert len(calls) == 1
    assert result["lawyers"]["positive"]["projects"][0]["kind"] == "unknown"
    assert result["judge"]["strengths"] == []
    assert result["judge"]["verdict"] == "needs_more_evidence"


def test_required_skill_claim_fails_even_if_model_verifier_approves(monkeypatch):
    inputs = {"job": {"job_id": "j", "required_skills": ["SQL"]},
              "requirements": [{"id": "required:1", "kind": "required", "text": "SQL"}],
              "depth_projects": [{"dimensions": {"implementation": {"score": 2}}}],
              "evidence": [{"id": "depth:e:E1", "source": "depth_repository", "location": "route.java",
                            "excerpt": "Java shuttle planner"}]}
    def fake_lawyer(model, role, requirements, evidence, depth_projects, positive_review=None):
        result = {category: [] for category in review.lawyers.CATEGORIES}
        if role == "positive":
            result["skills_required_knowledge"] = [{"text": "Demonstrated SQL",
                                                     "evidence_ids": ["depth:e:E1"], "kind": "artifact_evidence"}]
        return result
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    monkeypatch.setattr(review, "verify_findings", lambda model, findings, requirements, evidence: findings)
    result = review.run_review(inputs)
    assert result["lawyers"]["positive"]["skills_required_knowledge"][0]["kind"] == "unknown"
    assert result["judge"]["verdict"] == "needs_more_evidence"


def test_project_citation_does_not_become_work_experience():
    findings = {category: [] for category in review.lawyers.CATEGORIES}
    findings["work_experience"] = [{"text": "Built a route planner as work experience.",
                                    "evidence_ids": ["profile:project:1", "paralegal:1"],
                                    "kind": "supported_claim"}]
    evidence = [{"id": "profile:project:1", "source": "resume_claim", "location": "project/p/summary", "excerpt": "Route planner"},
                {"id": "paralegal:1", "source": "resume_claim", "location": "prior_experience", "excerpt": "Built a route planner"}]
    assert review._keep_category_evidence(findings, evidence)["work_experience"] == []


def test_pending_project_blocks_review_after_other_project_fails(client, monkeypatch):
    client.post("/api/auth/signup", json={"email": "pending@example.com", "password": "DemoPass123!"})
    user = api.store.user_for_session(client.cookies.get("sc_session"))
    case_id = "mixed-depth-status"
    api.store.put_case(case_id, user["id"], {
        "case_id": case_id, "candidate": {"candidate_id": user["id"], "resume_text": "", "skills": {}},
        "job": {"job_id": "test", "required_skills": ["Python"]},
        "projects": [{"project": {"id": "failed"}, "evaluation_id": "e1"},
                     {"project": {"id": "running"}, "evaluation_id": "e2"}],
    })
    monkeypatch.setattr(cases, "get_depth", lambda key: {"status": "failed" if key == "e1" else "running",
                                                        "result": None, "error": None})
    assert client.get(f"/api/cases/{case_id}").json()["status"] == "pending"
    assert client.get(f"/api/cases/{case_id}/review-preview").status_code == 409
    assert client.post(f"/api/cases/{case_id}/review").status_code == 409


def test_pasted_job_to_review_with_real_peer_adapters(client, monkeypatch):
    assert client.post("/api/auth/signup", json={"email": "trial@example.com", "password": "DemoPass123!"}).status_code == 200
    client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"})
    client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"Built a Python REST API with unit tests and SQL persistence.")})
    client.patch("/api/onboarding/interests", json={"interests": "Software engineering", "target_tracks": ["CS"]})
    client.patch("/api/onboarding/skills", json={"skills": {"CS": {"Python": 4, "APIs": 3}}})
    client.post("/api/onboarding/complete")
    project = client.post("/api/profile/resume-project", json={"title": "API", "summary": "Built a Python REST API with tests"}).json()["project"]
    client.patch("/api/profile/projects", json={"selected_ids": [project["id"]]})

    description = "Software engineer intern. Build Python REST APIs and SQL services. Required: Python, APIs, SQL. Preferred: React."
    parsed = client.post("/api/jobs/parse", json={"description": description}).json()
    assert parsed["track"] == "software"
    saved = client.post("/api/jobs/pasted", json={"description": description, "track": "software", "title": "Software Intern", "company": "Trial Co"})
    assert saved.status_code == 201
    job_id = saved.json()["job"]["job_id"]
    matches = client.get("/api/jobs/matches").json()["jobs"]
    assert any(item["source"] == "curated" for item in matches)
    pasted = next(item for item in matches if item["job_id"] == job_id)
    assert pasted["screening"]["stage"] == "profile_screen"

    monkeypatch.setattr(api, "start_depth", lambda *_: "evaluation-1")
    monkeypatch.setattr(cases, "get_depth", lambda _: {"status": "complete", "result": {
        "project_id": project["id"], "evaluation_mode": "codex", "confidence": "medium", "dimensions": {"skill_depth": {"score": 3, "evidence_ids": ["E1"]}},
        "demonstrated_skills": [{"skill": "Python", "evidence_ids": ["E1"]}], "limitations": [], "follow_up_questions": [],
        "evidence": [{"id": "E1", "source_type": "repository", "location": "api.py", "excerpt": "A tested Python API endpoint"}],
    }, "error": None})
    case_id = client.post("/api/cases", json={"job_id": job_id}).json()["case_id"]
    preview = client.get(f"/api/cases/{case_id}/review-preview")
    assert preview.status_code == 200
    assert preview.json()["paralegal"]["evidence"]
    assert preview.json()["synthetic_comparisons"]
    assert any(item["id"] == "depth:evaluation-1:E1" for item in preview.json()["evidence"])

    monkeypatch.setattr(api.review_pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(review, "verify_findings", lambda model, findings, requirements, evidence: findings)
    def fake_lawyer(model, role, requirements, evidence, depth_projects, positive_review=None):
        empty = {category: [] for category in review.lawyers.CATEGORIES}
        if role == "positive":
            empty["projects"] = [{"text": "The project includes a tested API endpoint.", "evidence_ids": ["depth:evaluation-1:E1"], "kind": "artifact_evidence"}]
        return empty
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    assert client.post(f"/api/cases/{case_id}/review").status_code == 202
    result = client.get(f"/api/cases/{case_id}/review").json()
    assert result["status"] == "complete"
    assert result["result"]["judge"]["verdict"] == "needs_more_evidence"
    assert result["result"]["categories"]["projects"]["pluses"][0]["evidence_ids"] == ["depth:evaluation-1:E1"]

    client.post("/api/auth/logout")
    client.post("/api/auth/signup", json={"email": "other@example.com", "password": "DemoPass123!"})
    assert client.get(f"/api/cases/{case_id}/review").status_code == 404


def test_ollama_depth_result_reaches_lawyers_without_relabeling_output():
    bundle = {"schema_version": 1, "case_id": "c1", "candidate": {"candidate_id": "a", "resume_text": "", "skills": {}},
              "job": {"job_id": "j", "track": "hardware", "required_skills": ["FPGA"]},
              "project_assessments": [{"project": {"id": "p", "summary": "FPGA design"}, "evaluation_id": "e1", "status": "complete",
                                       "result": {"project_id": "p", "evaluation_mode": "ollama", "dimensions": {"verification": {"score": 3, "evidence_ids": ["E1"]}},
                                                  "evidence": [{"id": "E1", "source_type": "repository", "location": "rtl.sv", "excerpt": "module fpga; endmodule"}]}}]}
    inputs = review.review_inputs(bundle)
    assert inputs["actual_depth_modes"] == ["ollama"]
    assert inputs["depth_projects"][0]["dimensions"]["verification"]["evidence_ids"] == ["depth:e1:E1"]
    assert bundle["project_assessments"][0]["result"]["evaluation_mode"] == "ollama"
