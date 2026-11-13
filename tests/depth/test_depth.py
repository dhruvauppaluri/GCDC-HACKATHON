from io import BytesIO
import base64
import time

from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pytest

from backend.depth import evaluation
from backend.depth import codex_adapter
from backend.depth.api import app
from backend.depth.fixtures import SCENARIOS
from backend.depth import ingestion
from backend.depth.ingestion import extract_upload, make_evidence, parse_github_url
from backend.depth.rubrics import ANSWER_CRITERIA, ARTIFACT_CRITERIA, RUBRICS


def test_all_three_mock_scenarios_and_answer_revision():
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
        assert updated["confidence"] == "low"
        assert updated["history"][0]["depth_score"] == initial["depth_score"]
        for name in ARTIFACT_CRITERIA[track]:
            assert updated["dimensions"][name] == initial["dimensions"][name]
        for name in ANSWER_CRITERIA[track]:
            assert updated["dimensions"][name]["evidence_ids"] == [updated["answers"][0]["evidence_id"]]
        assert set(updated["dimensions"]) == set(RUBRICS[track])


def test_missing_evidence_is_unassessed():
    result = evaluation.initial_assessment("x", "software", None, None, [], [], "mock")
    assert result["depth_score"] is None
    assert result["confidence"] == "unassessed"
    assert all(value is None for value in result["dimensions"].values())


def test_live_citation_gate_and_schema_parity(monkeypatch):
    evidence = make_evidence([{"source_type": "document", "location": "writeup", "text": "A project description"}])
    monkeypatch.setattr(evaluation, "llm_json", lambda *_: {
        "project_summary": "A project", "architecture_summary": "Unknown",
        "dimensions": {"scalability": {"score": 4, "evidence_ids": ["BAD"]}, "scenario_robustness": {"score": 2, "evidence_ids": ["E1"]}},
        "demonstrated_skills": [{"skill": "unsupported", "evidence_ids": ["BAD"]}, {"skill": "description", "evidence_ids": ["E1"]}],
        "unverified_skills": [], "follow_up_questions": [],
    })
    live = evaluation.initial_assessment("x", "software", None, None, evidence, [], "live")
    mock = evaluation.initial_assessment("x", "software", None, None, evidence, [], "mock")
    assert set(live) == set(mock)
    assert live["dimensions"]["scalability"] is None
    assert live["dimensions"]["scenario_robustness"]["score"] == 2
    assert [s["skill"] for s in live["demonstrated_skills"]] == ["description"]


def test_website_description_cannot_establish_implementation(monkeypatch):
    evidence = make_evidence([{"source_type": "website", "location": "https://example.com", "text": "We built a scalable Python app."}])
    monkeypatch.setattr(evaluation, "llm_json", lambda *_: {
        "dimensions": {"scalability": {"score": 2, "evidence_ids": ["E1"]}, "skill_execution": {"score": 4, "evidence_ids": ["E1"]}},
        "demonstrated_skills": [{"skill": "Python", "evidence_ids": ["E1"]}],
    })
    result = evaluation.initial_assessment("p", "software", None, None, evidence, [], "live", "https://example.com")
    assert result["website_url"] == "https://example.com"
    assert result["dimensions"]["skill_execution"] is None
    assert result["demonstrated_skills"] == []
    assert result["dimensions"]["scalability"]["score"] == 2


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


def test_public_website_extraction_is_bounded_and_rejects_private_dns(monkeypatch):
    monkeypatch.setattr(ingestion.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    with pytest.raises(ValueError, match="public address"):
        ingestion.validate_public_website_url("https://internal.example")
    monkeypatch.setattr(ingestion.socket, "getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("93.184.215.14", 443))])
    class Response:
        status_code = 200
        headers = {"content-type": "text/html"}
        def raise_for_status(self):
            pass
        def iter_bytes(self):
            yield b"<html><script>ignore me</script><main>Project details</main></html>"
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def stream(self, *args, **kwargs):
            return Response()
    monkeypatch.setattr(ingestion.httpx, "Client", Client)
    sources, limits = ingestion.public_website_evidence("https://example.com/project")
    assert sources[0]["source_type"] == "website"
    assert sources[0]["text"] == "Project details"
    assert limits == []


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


def test_codex_mode_uses_cli_and_preserves_answer_provenance(monkeypatch):
    evidence = make_evidence([{"source_type": "claim", "location": "project_text", "text": "I built a queue for API jobs."}])
    calls = []
    def fake_codex(system, content, **kwargs):
        calls.append(kwargs)
        if kwargs.get("answer_only"):
            return {"dimensions": {"scalability": {"score": 3, "evidence_ids": [content["answers"][0]["id"]]}, "scenario_robustness": None}}
        return {"project_summary": "Candidate claims an API queue.", "summary_evidence_ids": ["E1"], "architecture_summary": "Unverified", "architecture_evidence_ids": [], "dimensions": {name: None for name in RUBRICS["software"]}, "demonstrated_skills": [], "unverified_skills": ["queue design"], "follow_up_questions": [{"id": "Q1", "question": "Why a queue?"}]}
    monkeypatch.setattr(evaluation, "codex_json", fake_codex)
    initial = evaluation.initial_assessment("p", "software", None, None, evidence, [], "codex")
    assert initial["evaluation_mode"] == "codex"
    assert initial["depth_score"] is None
    assert any("self-reported" in text for text in initial["limitations"])
    revised = evaluation.revise_assessment(initial, [{"question_id": "Q1", "answer": "It absorbs bursts while the worker processes jobs."}])
    assert revised["depth_score"] == 7.5
    assert revised["confidence"] == "low"
    assert revised["dimensions"]["scalability"]["evidence_ids"] == ["E2"]
    assert calls == [{"dimensions": tuple(RUBRICS["software"])}, {"answer_only": True, "dimensions": ("scalability", "scenario_robustness")}]


def test_codex_cli_runs_ephemeral_read_only(monkeypatch):
    monkeypatch.setattr(codex_adapter.shutil, "which", lambda _: "/usr/local/bin/codex")
    def fake_run(command, **kwargs):
        assert "--ephemeral" in command
        assert command[command.index("--sandbox") + 1] == "read-only"
        assert "--output-schema" in command
        from pathlib import Path
        Path(command[command.index("--output-last-message") + 1]).write_text('{"dimensions": {"conceptual": null, "systems": null, "tradeoffs": null}}')
        return type("Result", (), {"returncode": 0})()
    monkeypatch.setattr(codex_adapter.subprocess, "run", fake_run)
    assert "dimensions" in codex_adapter.codex_json("Assess", {"answers": []}, answer_only=True)


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
        assert client.post("/depth/evaluations", data={"project_id": "old", "career_track": "business", "project_text": "test"}).status_code == 422
