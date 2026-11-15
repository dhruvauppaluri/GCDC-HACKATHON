"""Local trial: pasted jobs, claim extraction, Depth citations, and the review handoff."""
from fastapi.testclient import TestClient
import json
import pytest

from backend.web import api, cases, review
from backend.web import imports
from backend.web import paralegal
from backend.web.judge import rate
from data.fixtures.rishi import lawyers_grounded
from backend.web.jobs import parse_job_description, match_jobs
from backend.web.storage import Store


def test_github_import_uses_optional_token_and_reports_quota(monkeypatch):
    seen = {}
    class Response:
        status_code = 429
        headers = {"x-ratelimit-remaining": "0"}
    class Client:
        def __init__(self, **kwargs): seen.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, *args, **kwargs): return Response()
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(imports.httpx, "Client", Client)
    with pytest.raises(RuntimeError, match="GitHub API limit"):
        imports.import_github("https://github.com/example/repo")
    assert seen["headers"]["Authorization"] == "Bearer test-token"


def test_paralegal_extracts_only_exact_cited_spans(monkeypatch):
    sources = [{"id": "profile:resume", "source": "resume_claim", "location": "resume_text",
                "excerpt": "Built a Java route planner. Tested disconnected stops."}]
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return json.dumps({"message": {"content": json.dumps({"facts": [
            {"source_id": "profile:resume", "quote": "Built a Java route planner", "category": "project"}
        ]})}}).encode()
    monkeypatch.setattr(paralegal, "urlopen", lambda *args, **kwargs: Response())
    result = paralegal.extract_facts(sources)
    assert result["evidence"] == [{"source_id": "profile:resume", "quote": "Built a Java route planner", "category": "project"}]


def test_judge_rating_keeps_unknowns_out_of_exact_score():
    reqs = [{"id": "required:1", "kind": "required", "text": "Java"},
            {"id": "required:2", "kind": "required", "text": "SQL"},
            {"id": "preferred:1", "kind": "preferred", "text": "Python"}]
    evidence = [{"id": "depth:1", "source": "depth_repository", "excerpt": "Java route planner"},
                {"id": "resume:1", "source": "resume_claim", "excerpt": "Python coursework"}]
    positive = {category: [] for category in review.lawyers.CATEGORIES}
    negative = {category: [] for category in review.lawyers.CATEGORIES}
    positive["projects"] = [{"kind": "artifact_evidence", "text": "Built a Java route planner", "evidence_ids": ["depth:1"]}]
    positive["skills_required_knowledge"] = [{"kind": "supported_claim", "text": "Studied Python", "evidence_ids": ["resume:1"]}]
    result = rate(reqs, positive, negative, evidence, review._mentions_skill)
    assert result["score"] is None
    assert result["score_range"] == [50, 94]
    assert [row["status"] for row in result["requirements"]] == ["artifact_supported", "unknown", "claimed"]


def test_judge_does_not_display_zero_to_hundred_for_no_evidence():
    reqs = [{"id": "required:1", "kind": "required", "text": "SQL"}]
    empty = {category: [] for category in review.lawyers.CATEGORIES}
    result = rate(reqs, empty, empty, [], review._mentions_skill)
    assert result["rating"] == "unassessed"
    assert result["score_range"] is None


def test_uncited_lawyer_finding_cannot_stop_entire_review():
    findings = {category: [] for category in review.lawyers.CATEGORIES}
    findings["projects"] = [{"text": "Built SQL storage", "evidence_ids": [], "kind": "supported_claim"}]
    validated = review.lawyers.validate(findings, [], [])
    assert validated["projects"][0]["kind"] == "unknown"


def test_activity_citation_cannot_be_promoted_to_project_or_job():
    findings = {category: [] for category in review.lawyers.CATEGORIES}
    findings["projects"] = [{"text": "Real-world project", "evidence_ids": ["paralegal:1"], "kind": "supported_claim"}]
    findings["work_experience"] = [{"text": "Worked in a job", "evidence_ids": ["paralegal:1"], "kind": "supported_claim"}]
    evidence = [{"id": "paralegal:1", "source": "resume_claim", "location": "resume_text",
                 "excerpt": "Built an API", "category": "other"}]
    filtered = review._keep_category_evidence(findings, evidence)
    assert filtered["projects"] == []
    assert filtered["work_experience"] == []


def test_failed_review_can_be_restarted(tmp_path):
    store = Store(tmp_path / "retry.sqlite3")
    store.put_review("case", "candidate")
    store.finish_review("case", error="Ollama timed out")
    assert store.get_review("case", "candidate")["status"] == "failed"
    store.put_review("case", "candidate")
    restarted = store.get_review("case", "candidate")
    assert restarted == {"status": "pending", "result": None, "error": None}


def test_paralegal_rejects_fabricated_quote(monkeypatch):
    sources = [{"id": "profile:resume", "source": "resume_claim", "location": "resume_text", "excerpt": "Java route planner"}]
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return json.dumps({"message": {"content": json.dumps({"facts": [
            {"source_id": "profile:resume", "quote": "SQL database", "category": "skill"}
        ]})}}).encode()
    monkeypatch.setattr(paralegal, "urlopen", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="absent"):
        paralegal.extract_facts(sources)


def test_paralegal_does_not_treat_career_goal_or_generic_experience_as_job(monkeypatch):
    excerpt = "Experience: Built a route planner. Seeking software internships."
    sources = [{"id": "profile:resume", "source": "resume_claim", "location": "resume_text", "excerpt": excerpt}]
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, *args): return json.dumps({"message": {"content": json.dumps({"facts": [
            {"source_id": "profile:resume", "quote": excerpt, "category": "work_experience"}
        ]})}}).encode()
    monkeypatch.setattr(paralegal, "urlopen", lambda *args, **kwargs: Response())
    facts = paralegal.extract_facts(sources)["evidence"]
    assert facts == [{"source_id": "profile:resume", "quote": "Experience: Built a route planner", "category": "other"}]


def test_review_passes_paralegal_facts_to_both_lawyers(monkeypatch):
    inputs = {"job": {"job_id": "j", "required_skills": []}, "requirements": [], "depth_projects": [],
              "evidence": [{"id": "profile:resume", "source": "resume_claim", "location": "resume_text", "excerpt": "Built an API"}]}
    monkeypatch.setattr(review, "extract_facts", lambda evidence: {"source": "ollama_paralegal", "evidence": [
        {"source_id": "profile:resume", "quote": "Built an API", "category": "project"}]})
    seen = []
    def fake_lawyer(model, role, requirements, evidence, depth_projects, positive_review=None):
        seen.append((role, [item for item in evidence if item["id"].startswith("paralegal:")]))
        return {category: [] for category in review.lawyers.CATEGORIES}
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    monkeypatch.setattr(review, "verify_findings", lambda model, findings, requirements, evidence: findings)
    result = review.run_review(inputs)
    assert [role for role, _ in seen] == ["positive", "negative"]
    assert all(items[0]["excerpt"] == "Built an API" for _, items in seen)
    assert result["paralegal"]["source"] == "ollama_paralegal"


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


def test_preferred_only_match_does_not_get_worth_exploring():
    profile = {"target_tracks": ["HW"], "skills": {"HW": {"Python": 4}}, "projects": []}
    job = {"job_id": "embedded", "track": "hardware", "title": "Embedded Intern", "company": "Demo",
           "required_skills": ["C", "embedded systems"], "preferred_skills": ["Python"]}
    result = match_jobs(profile, [job])[0]
    assert result["matched_skills"] == ["Python"]
    assert result["screening"]["verdict"] == "more_info_needed"


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
    monkeypatch.setattr(review, "extract_facts", lambda evidence: {"source": "ollama_paralegal", "evidence": []})
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
    assert result["lawyers"]["positive"]["projects"] == []
    assert result["judge"]["strengths"] == []
    assert result["judge"]["verdict"] == "needs_more_evidence"


def test_required_skill_claim_fails_even_if_model_verifier_approves(monkeypatch):
    monkeypatch.setattr(review, "extract_facts", lambda evidence: {"source": "ollama_paralegal", "evidence": []})
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
    assert result["lawyers"]["positive"]["skills_required_knowledge"] == []
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
    assert preview.json()["paralegal"]["source"] == "pending_model_extraction"
    assert any(item["id"] == "depth:evaluation-1:E1" for item in preview.json()["evidence"])

    monkeypatch.setattr(api.review_pool, "submit", lambda fn, *args: fn(*args))
    monkeypatch.setattr(review, "extract_facts", lambda evidence: {"source": "ollama_paralegal", "evidence": []})
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
