from io import BytesIO
import base64
import time

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pytest

from backend.depth import evaluation
from backend.depth.api import app
from backend.depth.fixtures import SCENARIOS
from backend.depth import ingestion
from backend.depth.ingestion import extract_upload, make_evidence, parse_github_url


def test_all_four_mock_scenarios_and_answer_revision():
    for track, fixture in SCENARIOS.items():
        evidence = make_evidence([{"source_type": "claim", "location": "project_text", "text": fixture["text"]}])
        initial = evaluation.initial_assessment(track, track, None, None, evidence, [], "mock")
        assert initial["evaluation_mode"] == "mock"
        assert initial["depth_score"] is None
        assert initial["unverified_skills"]
        assert not initial["demonstrated_skills"]
        updated = evaluation.revise_assessment(initial, [{"question_id": "Q1", "answer": fixture["answer"]}])
        assert updated["revision"] == 1
        assert updated["depth_score"] != initial["depth_score"]
        assert updated["history"][0]["depth_score"] == initial["depth_score"]
        assert updated["dimensions"]["implementation"] == initial["dimensions"]["implementation"]
        assert updated["dimensions"]["validation"] == initial["dimensions"]["validation"]
        assert updated["dimensions"]["conceptual"]["evidence_ids"] == [updated["answers"][0]["evidence_id"]]


def test_missing_evidence_is_unassessed():
    result = evaluation.initial_assessment("x", "software", None, None, [], [], "mock")
    assert result["depth_score"] is None
    assert result["confidence"] == "unassessed"
    assert all(value is None for value in result["dimensions"].values())


def test_live_citation_gate_and_schema_parity(monkeypatch):
    evidence = make_evidence([{"source_type": "document", "location": "writeup", "text": "A project description"}])
    monkeypatch.setattr(evaluation, "llm_json", lambda *_: {
        "project_summary": "A project", "architecture_summary": "Unknown",
        "dimensions": {"conceptual": {"score": 4, "evidence_ids": ["BAD"]}, "systems": {"score": 2, "evidence_ids": ["E1"]}},
        "demonstrated_skills": [{"skill": "unsupported", "evidence_ids": ["BAD"]}, {"skill": "description", "evidence_ids": ["E1"]}],
        "unverified_skills": [], "follow_up_questions": [],
    })
    live = evaluation.initial_assessment("x", "software", None, None, evidence, [], "live")
    mock = evaluation.initial_assessment("x", "software", None, None, evidence, [], "mock")
    assert set(live) == set(mock)
    assert live["dimensions"]["conceptual"] is None
    assert live["dimensions"]["systems"]["score"] == 2
    assert [s["skill"] for s in live["demonstrated_skills"]] == ["description"]


def test_extract_upload_formats():
    assert extract_upload("notes.txt", b"hello") == "hello"
    assert extract_upload("notes.md", b"# hello") == "# hello"
    doc = Document()
    doc.add_paragraph("Word evidence")
    buffer = BytesIO()
    doc.save(buffer)
    assert "Word evidence" in extract_upload("notes.docx", buffer.getvalue())
    pdf = PdfWriter()
    pdf.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    pdf.write(buffer)
    assert extract_upload("notes.pdf", buffer.getvalue()) == ""
    with pytest.raises(ValueError):
        extract_upload("bad.exe", b"test")


def test_public_github_url_validation():
    assert parse_github_url("https://github.com/example/repo") == ("example", "repo")
    for url in ["http://github.com/a/b", "https://evil.example/a/b", "https://github.com/a/b/tree/main", "https://user:pass@github.com/a/b"]:
        with pytest.raises(ValueError):
            parse_github_url(url)


def test_repository_ingestion_pins_commit_and_reads_source(monkeypatch):
    class Response:
        def __init__(self, body):
            self.body = body
        def raise_for_status(self):
            pass
        def json(self):
            return self.body
    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            if url.endswith("/repos/example/repo"):
                return Response({"private": False, "default_branch": "main"})
            if url.endswith("/commits/main"):
                return Response({"sha": "abc123"})
            if url.endswith("/git/trees/abc123"):
                return Response({"tree": [{"type": "blob", "path": "tests/test_app.py", "size": 20, "sha": "blob123"}]})
            if url.endswith("/git/blobs/blob123"):
                return Response({"encoding": "base64", "content": base64.b64encode(b"assert works()\n").decode()})
            raise AssertionError(url)
    monkeypatch.setattr(ingestion.httpx, "Client", Client)
    sha, sources, limitations = ingestion.public_repository_evidence("https://github.com/example/repo")
    assert sha == "abc123"
    assert sources == [{"source_type": "repository", "location": "tests/test_app.py@abc123", "text": "assert works()\n"}]
    assert not limitations


def test_live_adapter_uses_configured_model(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DEPTH_MODEL", "test-model")
    class Response:
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}]}
    def fake_post(url, **kwargs):
        assert url == "https://api.openai.com/v1/chat/completions"
        assert kwargs["json"]["model"] == "test-model"
        assert kwargs["json"]["response_format"] == {"type": "json_object"}
        return Response()
    monkeypatch.setattr(evaluation.httpx, "post", fake_post)
    assert evaluation.llm_json("Assess", {"track": "software"}) == {"ok": True}


def wait_for(client, job_id):
    for _ in range(100):
        data = client.get(f"/depth/evaluations/{job_id}").json()
        if data["status"] in {"complete", "failed"}:
            return data
        time.sleep(0.02)
    pytest.fail("Job did not complete")


def test_async_api_and_failure(monkeypatch):
    with TestClient(app) as client:
        fixture = SCENARIOS["software"]
        response = client.post("/depth/evaluations", data={"project_id": "demo", "career_track": "software", "project_text": fixture["text"], "mode": "mock"})
        assert response.status_code == 202
        job_id = response.json()["evaluation_id"]
        completed = wait_for(client, job_id)
        assert completed["status"] == "complete"
        assert completed["result"]["depth_score"] is None
        answer = client.post(f"/depth/evaluations/{job_id}/answers", json={"answers": [{"question_id": "Q1", "answer": fixture["answer"]}]})
        assert answer.status_code == 202
        revised = wait_for(client, job_id)
        assert revised["result"]["revision"] == 1
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        response = client.post("/depth/evaluations", data={"project_id": "failure", "career_track": "software", "project_text": "plain text", "mode": "live"})
        failed = wait_for(client, response.json()["evaluation_id"])
        assert failed["status"] == "failed"
        assert "OPENAI_API_KEY" in failed["error"]
