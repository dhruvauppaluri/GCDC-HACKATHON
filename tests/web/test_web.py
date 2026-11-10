from fastapi.testclient import TestClient
import json
import pytest

from backend.web import api
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
