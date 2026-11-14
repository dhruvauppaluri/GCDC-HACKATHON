from fastapi.testclient import TestClient
import json
import pytest

from backend.web import api
from backend.web import cases
from backend.web.jobs import match_jobs, suggest_tracks
from backend.web.storage import Store
from scripts.seed_web_demo import FIXTURES, PASSWORD, main as seed_demo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "store", Store(tmp_path / "test.sqlite3"))
    return TestClient(api.app)


def signup(client):
    response = client.post("/api/auth/signup", json={"email": "New@Example.com", "password": "DemoPass123!"})
    assert response.status_code == 200
    assert response.json()["email"] == "new@example.com"


def test_signup_login_resume_and_return(client):
    signup(client)
    assert client.post("/api/auth/signup", json={"email": "new@example.com", "password": "DemoPass123!"}).status_code == 409
    assert client.post("/api/onboarding/complete").status_code == 409
    assert client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"}).status_code == 200
    assert client.post("/api/onboarding/resume", files={"file": ("resume.docx", b"x")}).status_code == 422
    assert client.post("/api/onboarding/resume", files={"file": ("resume.txt", b" ")}).status_code == 422
    assert client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"x" * 2_000_001)}).status_code == 413
    assert client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"Built FPGA boards and software tools")}).status_code == 200
    assert client.get("/api/me").json()["profile"]["resume_name"] == "resume.txt"
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "new@example.com", "password": "DemoPass123!"}).status_code == 200
    assert client.get("/api/me").json()["profile"]["first_name"] == "Ada"
    assert client.get("/api/me").json()["profile"]["completed"] is False


def test_multiple_tracks_skills_matches_and_research(client, tmp_path, monkeypatch):
    signup(client)
    client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"})
    client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"I built an FPGA and React app")})
    assert suggest_tracks("FPGA chip design and embedded systems") == ["HW"]
    assert suggest_tracks("FPGA and web apps") == ["CS", "HW"]
    assert suggest_tracks("the moon") == []
    assert client.patch("/api/onboarding/interests", json={"interests": "FPGA and web apps", "target_tracks": ["HW", "CS"]}).status_code == 200
    assert client.patch("/api/onboarding/skills", json={"skills": {"HW": {"FPGA": 6}, "CS": {"React": 3}}}).status_code == 422
    assert client.patch("/api/onboarding/skills", json={"skills": {"HW": {"FPGA": 4}, "CS": {"React": 3}}}).status_code == 200
    assert client.post("/api/onboarding/complete").status_code == 200
    exported = client.get("/api/profile/export").json()
    assert exported["target_tracks"] == ["hardware", "software"]
    assert "I built an FPGA" in exported["resume_text"]
    jobs = client.get("/api/jobs/matches").json()["jobs"]
    assert jobs and all(j["track"] in {"hardware", "software"} for j in jobs)
    assert any("FPGA" in j["matched_skills"] for j in jobs)
    research = tmp_path / "research.json"
    research.write_text('[{"job_id":"r1","track":"hardware","title":"Circuit Intern","company":"Research Co","required_skills":["FPGA"],"preferred_skills":[]}]')
    monkeypatch.setenv("RESEARCH_JOBS_FILE", str(research))
    assert any(j["source"] == "research" for j in client.get("/api/jobs/matches").json()["jobs"])
    client.patch("/api/onboarding/interests", json={"interests": "FPGA, software, and product", "target_tracks": ["HW", "CS", "PM"]})
    assert client.get("/api/me").json()["profile"]["completed"] is False
    assert client.get("/api/jobs/matches").status_code == 409


def test_links_and_import_failure_preserves_profile(client, monkeypatch):
    signup(client)
    assert client.patch("/api/profile/links", json={"github_url": "http://github.com/a"}).status_code == 422
    assert client.patch("/api/profile/links", json={"github_url": "https://github.com/example", "website_url": ""}).status_code == 200
    monkeypatch.setattr(api, "import_github", lambda _: (_ for _ in ()).throw(ValueError("unavailable")))
    result = client.post("/api/profile/import")
    assert result.status_code == 200 and result.json()["errors"]
    assert client.get("/api/me").json()["profile"]["github_url"] == "https://github.com/example"
    assert client.get("/api/me").json()["profile"]["projects"] == []
    monkeypatch.setattr(api, "import_github", lambda _: [{"id": "github:a/b", "source": "github", "title": "b", "url": "https://github.com/a/b", "summary": "demo", "selected": False}])
    assert client.post("/api/profile/import").json()["projects"][0]["selected"] is False
    assert client.patch("/api/profile/projects", json={"selected_ids": ["github:a/b"]}).status_code == 200
    assert client.get("/api/me").json()["profile"]["projects"][0]["selected"] is True
    assert client.get("/api/profile/export").json()["projects"][0]["title"] == "b"
    assert client.patch("/api/profile/links", json={"github_url": "https://github.com/another"}).status_code == 200
    assert client.get("/api/me").json()["profile"]["projects"] == []


def test_partial_reimport_preserves_selected_projects_from_failed_source(client, monkeypatch):
    signup(client)
    monkeypatch.setattr(api, "validate_public_url", lambda *_: None)
    client.patch("/api/profile/links", json={"github_url": "https://github.com/example", "website_url": "https://portfolio.example"})
    monkeypatch.setattr(api, "import_github", lambda _: [{"id": "github:example/old", "source": "github", "title": "old", "url": "https://github.com/example/old", "summary": "old", "selected": False}])
    monkeypatch.setattr(api, "import_website", lambda _: [{"id": "website:portfolio.example", "source": "website", "title": "portfolio", "url": "https://portfolio.example", "summary": "work", "selected": False}])
    assert client.post("/api/profile/import").status_code == 200
    client.patch("/api/profile/projects", json={"selected_ids": ["website:portfolio.example"], "contributions": {"website:portfolio.example": "I designed the site"}})
    monkeypatch.setattr(api, "import_github", lambda _: [{"id": "github:example/new", "source": "github", "title": "new", "url": "https://github.com/example/new", "summary": "new", "selected": False}])
    monkeypatch.setattr(api, "import_website", lambda _: (_ for _ in ()).throw(ValueError("temporarily unavailable")))
    result = client.post("/api/profile/import").json()
    assert result["errors"]
    assert {item["id"] for item in result["projects"]} == {"github:example/new", "website:portfolio.example"}
    website = next(item for item in result["projects"] if item["source"] == "website")
    assert website["selected"] is True
    assert website["contribution"] == "I designed the site"


def test_matching_does_not_claim_fit_probability():
    profile = {"target_tracks": ["PM"], "skills": {"PM": {"user research": 3}}, "projects": [{"title": "Research notes", "summary": "Interviewed users for user research", "selected": True}]}
    jobs = [{"job_id": "j", "track": "product", "title": "PM", "company": "A", "required_skills": ["user research", "analytics"], "preferred_skills": []}]
    result = match_jobs(profile, jobs)[0]
    assert result["matched_skills"] == ["user research"]
    assert result["skill_gaps"] == ["analytics"]
    assert result["project_context"] == ["Research notes"]
    assert "fit_score" not in result


def test_synthetic_user_resumes_and_idempotent_seed(tmp_path, monkeypatch):
    fixtures = [json.loads(path.read_text()) for path in sorted(FIXTURES.glob("*.json"))]
    assert len(fixtures) >= 12
    assert len({item["email"] for item in fixtures}) == len(fixtures)
    assert all(item["email"].endswith("@orbit.local") for item in fixtures)
    assert {track for item in fixtures for track in item["profile"].get("target_tracks", [])} == {"HW", "CS", "PM"}
    assert sum(not item["profile"]["completed"] for item in fixtures) >= 2
    for item in fixtures:
        profile = item["profile"]
        if profile["completed"]:
            assert len(profile["resume_text"]) >= 80
            assert all(profile["skills"].get(track) for track in profile["target_tracks"])
        assert all(1 <= level <= 5 for values in profile.get("skills", {}).values() for level in values.values())
    monkeypatch.setenv("WEB_DATA_DIR", str(tmp_path))
    seed_demo()
    seed_demo()
    store = Store(tmp_path / "app.sqlite3")
    monkeypatch.setattr(api, "store", store)
    with TestClient(api.app) as client:
        for item in fixtures:
            response = client.post("/api/auth/login", json={"email": item["email"], "password": PASSWORD})
            assert response.status_code == 200
            profile = client.get("/api/me").json()["profile"]
            assert profile["completed"] == item["profile"]["completed"]
            if profile["completed"]:
                assert client.get("/api/jobs/matches").json()["jobs"]
                assert client.get("/api/profile/export").json()["resume_text"] == item["profile"]["resume_text"]
            else:
                assert client.get("/api/jobs/matches").status_code == 409
            client.post("/api/auth/logout")


def test_selected_project_case_handoff_and_user_isolation(client, monkeypatch):
    signup(client)
    client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"})
    client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"I built a Python API.")})
    client.patch("/api/onboarding/interests", json={"interests": "software", "target_tracks": ["CS"]})
    client.patch("/api/onboarding/skills", json={"skills": {"CS": {"Python": 4}}})
    client.post("/api/onboarding/complete")
    added = client.post("/api/profile/resume-project", json={"title": "Resume API", "summary": "I built an API"})
    assert added.status_code == 200
    resume_id = added.json()["project"]["id"]
    assert added.json()["project"]["source"] == "resume"
    monkeypatch.setattr(api, "import_github", lambda _: [{"id": "github:ada/api", "source": "github", "title": "API", "url": "https://github.com/ada/api", "summary": "A Python API", "selected": False}])
    client.patch("/api/profile/links", json={"github_url": "https://github.com/ada"})
    client.post("/api/profile/import")
    assert {p["id"] for p in client.get("/api/me").json()["profile"]["projects"]} == {"github:ada/api", resume_id}
    assert client.post("/api/cases", json={"job_id": "cs-1"}).status_code == 422
    client.patch("/api/profile/projects", json={"selected_ids": ["github:ada/api"], "contributions": {"github:ada/api": "I implemented the API endpoints"}})
    started = []
    def fake_start(project, track):
        started.append((project["id"], track, project.get("contribution")))
        return "evaluation-1"
    monkeypatch.setattr(api, "start_depth", fake_start)
    monkeypatch.setattr(cases, "get_depth", lambda _: {"status": "complete", "result": {
        "project_summary": "A Python API", "depth_score": 7.5, "confidence": "low", "dimensions": {},
        "demonstrated_skills": [{"skill": "Python", "evidence_ids": ["E1"]}],
        "follow_up_questions": [{"id": "Q1", "question": "How does it scale?"}],
        "evidence": [{"id": "E1", "source_type": "repository", "location": "api.py@abc:L1-L3", "excerpt": "def api(): pass"}],
    }, "error": None})
    response = client.post("/api/cases", json={"job_id": "cs-1"})
    assert response.status_code == 202
    assert started == [("github:ada/api", "software", "I implemented the API endpoints")]
    case_id = response.json()["case_id"]
    bundle = client.get(f"/api/cases/{case_id}").json()
    assert bundle["schema_version"] == 1
    assert bundle["status"] == "complete"
    assert bundle["candidate"]["resume_text"] == "I built a Python API."
    assert bundle["citations"][0]["ref"] == "depth:evaluation-1:E1"
    assert bundle["preparation"]["required_skills_with_project_evidence"] == ["Python"]
    assert "SQL" in bundle["preparation"]["required_skills_without_project_evidence"]
    client.post("/api/auth/logout")
    assert client.post("/api/auth/signup", json={"email": "other@example.com", "password": "DemoPass123!"}).status_code == 200
    assert client.get(f"/api/cases/{case_id}").status_code == 404


def test_depth_handoff_labels_contribution_as_claim(monkeypatch):
    sent = []
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"evaluation_id": "e1"}
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, data):
            sent.append(data)
            return Response()
    monkeypatch.setattr(cases.httpx, "Client", Client)
    project = {"id": "github:a/b", "source": "github", "url": "https://github.com/a/b", "summary": "Repository description", "contribution": "I wrote the worker"}
    assert cases.start_depth(project, "software") == "e1"
    assert sent[0]["repository_url"] == project["url"]
    assert sent[0]["project_text"] == "I wrote the worker"
    project["contribution"] = ""
    cases.start_depth(project, "software")
    assert "project_text" not in sent[1]


def test_case_keeps_project_link_when_depth_start_fails(client, monkeypatch):
    signup(client)
    client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"})
    client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"I built an API")})
    client.patch("/api/onboarding/interests", json={"interests": "software", "target_tracks": ["CS"]})
    client.patch("/api/onboarding/skills", json={"skills": {"CS": {"Python": 4}}})
    client.post("/api/onboarding/complete")
    monkeypatch.setattr(api, "import_github", lambda _: [{"id": "github:ada/api", "source": "github", "title": "API", "url": "https://github.com/ada/api", "summary": "API", "selected": False}])
    client.patch("/api/profile/links", json={"github_url": "https://github.com/ada"})
    client.post("/api/profile/import")
    client.patch("/api/profile/projects", json={"selected_ids": ["github:ada/api"]})
    monkeypatch.setattr(api, "start_depth", lambda *_: (_ for _ in ()).throw(ValueError("offline")))
    response = client.post("/api/cases", json={"job_id": "cs-1"})
    assert response.status_code == 202
    assert response.json()["status"] == "partial"
    case = client.get(f"/api/cases/{response.json()['case_id']}").json()
    assert case["status"] == "partial"
    assert case["project_assessments"][0]["project"]["url"] == "https://github.com/ada/api"
    assert case["project_assessments"][0]["status"] == "unavailable"


def test_website_link_reaches_depth_and_lawyer_bundle(client, monkeypatch):
    signup(client)
    client.patch("/api/onboarding/name", json={"first_name": "Ada", "last_name": "Lovelace"})
    client.post("/api/onboarding/resume", files={"file": ("resume.txt", b"I designed a product website")})
    client.patch("/api/onboarding/interests", json={"interests": "product", "target_tracks": ["PM"]})
    client.patch("/api/onboarding/skills", json={"skills": {"PM": {"user research": 4}}})
    client.post("/api/onboarding/complete")
    monkeypatch.setattr(api, "validate_public_url", lambda *_: None)
    client.patch("/api/profile/links", json={"website_url": "https://portfolio.example/work"})
    monkeypatch.setattr(api, "import_website", lambda _: [{"id": "website:portfolio.example", "source": "website", "title": "portfolio", "url": "https://portfolio.example/work", "summary": "My product work", "selected": False}])
    client.post("/api/profile/import")
    client.patch("/api/profile/projects", json={"selected_ids": ["website:portfolio.example"], "contributions": {"website:portfolio.example": "I designed the onboarding study"}})
    captured = []
    monkeypatch.setattr(api, "start_depth", lambda project, track: captured.append((project, track)) or "website-evaluation")
    monkeypatch.setattr(cases, "get_depth", lambda _: {"status": "complete", "result": {"demonstrated_skills": [], "follow_up_questions": [], "evidence": []}, "error": None})
    case_id = client.post("/api/cases", json={"job_id": "pm-1"}).json()["case_id"]
    assert captured[0][0]["url"] == "https://portfolio.example/work"
    assert captured[0][1] == "product"
    bundle = client.get(f"/api/cases/{case_id}").json()
    assert bundle["candidate"]["links"]["website_url"] == "https://portfolio.example/work"
    assert bundle["candidate"]["projects"][0]["url"] == "https://portfolio.example/work"
    assert bundle["project_assessments"][0]["project"]["contribution"] == "I designed the onboarding study"
