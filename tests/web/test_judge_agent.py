"""The model Judge must see both arguments and return grounded findings."""
import pytest

from backend.web import judge_agent


def fixture_case():
    inputs = {"job": {"title": "Software Intern", "company": "Example", "track": "software"},
              "requirements": [{"id": "required:1", "kind": "required", "text": "Python"}],
              "evidence": [{"id": "depth:e:E1", "source": "depth_repository", "location": "api.py", "excerpt": "Python endpoint"},
                           {"id": "paralegal:1", "source": "resume_claim", "signal": "Python", "excerpt": "Built a Python API"}]}
    positive = {"projects": [{"text": "Python endpoint exists", "evidence_ids": ["depth:e:E1"], "kind": "artifact_evidence"}],
                "work_experience": [], "skills_required_knowledge": []}
    negative = {"projects": [], "work_experience": [], "skills_required_knowledge": [
        {"text": "Ownership is unknown", "evidence_ids": [], "kind": "unknown"}]}
    baseline = {"match_score": 75, "verdict": "promising_documented_match", "eligibility": "unknown",
                "requirements": [{"id": "required:1", "text": "Python", "kind": "required", "status": "inspected artifact",
                                  "evidence_ids": ["depth:e:E1"], "coverage": 1}]}
    return inputs, positive, negative, baseline


def output():
    return {"recommendation": "consider", "reasoning": "The cited endpoint supports Python, while ownership remains unclear.",
            "strengths": [{"text": "The repository shows a Python endpoint.", "requirement_id": "required:1", "evidence_ids": ["depth:e:E1"]}],
            "concerns": [{"text": "Personal ownership is not verified.", "requirement_id": "required:1", "evidence_ids": []}],
            "eligibility_note": "Eligibility has not been verified."}


def test_gemini_judge_receives_both_lawyers_and_paralegal(monkeypatch):
    inputs, positive, negative, baseline = fixture_case()
    calls = []
    def fake_generate(system, content, schema, **kwargs):
        calls.append((system, content, schema, kwargs))
        return output()
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setattr(judge_agent, "generate_json", fake_generate)
    decision = judge_agent.adjudicate(inputs, positive, negative, baseline)
    assert decision["status"] == "complete"
    assert decision["recommendation"] == "consider"
    assert calls[0][1]["advocate"] == positive
    assert calls[0][1]["skeptic"] == negative
    assert calls[0][1]["paralegal_claim_signals"][0]["signal"] == "Python"
    assert calls[0][1]["documented_coverage"]["match_score"] == 75
    assert decision["eligibility_note"].startswith("Eligibility remains unverified")


def test_judge_rejects_invented_citation_and_uncited_strength(monkeypatch):
    inputs, positive, negative, baseline = fixture_case()
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    invented = output()
    invented["strengths"][0]["evidence_ids"] = ["made-up"]
    monkeypatch.setattr(judge_agent, "generate_json", lambda *_args, **_kwargs: invented)
    with pytest.raises(ValueError, match="unknown evidence"):
        judge_agent.adjudicate(inputs, positive, negative, baseline)
    invented["strengths"][0]["evidence_ids"] = []
    with pytest.raises(ValueError, match="needs cited evidence"):
        judge_agent.adjudicate(inputs, positive, negative, baseline)


def test_judge_does_not_present_uncovered_requirement_as_strength(monkeypatch):
    inputs, positive, negative, baseline = fixture_case()
    baseline["match_score"] = 0
    baseline["requirements"][0]["coverage"] = 0
    baseline["requirements"][0]["status"] = "not_shown"
    monkeypatch.setenv("JUDGE_PROVIDER", "gemini")
    monkeypatch.setattr(judge_agent, "generate_json", lambda *_args, **_kwargs: output())
    decision = judge_agent.adjudicate(inputs, positive, negative, baseline)
    assert decision["strengths"] == []
