"""The Judge must be reproducible and willing to report a weak documented fit."""
from backend.web.judge import judge_case
from backend.web import review


def case():
    return {"job": {"description_status": "full", "eligibility_requirements": []},
            "requirements": [{"id": "required:1", "kind": "required", "text": "Python"},
                             {"id": "required:2", "kind": "required", "text": "SQL"},
                             {"id": "preferred:1", "kind": "preferred", "text": "React"}],
            "evidence": [{"id": "depth:e:E1", "source": "depth_repository", "excerpt": "Python endpoint"},
                         {"id": "profile:resume", "source": "resume_claim", "excerpt": "Candidate reports Python"}]}


def empty():
    return {category: [] for category in review.lawyers.CATEGORIES}


def test_judge_reports_low_score_when_most_requirements_are_unsupported():
    positive, negative = empty(), empty()
    positive["projects"] = [{"text": "The Python project has a tested endpoint.",
                             "kind": "artifact_evidence", "evidence_ids": ["depth:e:E1"]}]
    negative["skills_required_knowledge"] = [{"text": "SQL and React remain unverified.",
                                                "kind": "unknown", "evidence_ids": []}]
    result = judge_case(case(), positive, negative)
    assert result["match_score"] == 52
    assert result["verdict"] == "partial_documented_match"
    assert [item["status"] for item in result["requirements"]] == ["inspected artifact", "not_shown", "not_shown"]
    assert result["objections"][0]["merit"] == "unknown"


def test_repeating_claims_cannot_raise_score_and_artifact_has_more_merit():
    positive, negative = empty(), empty()
    claim = {"text": "The candidate reports Python experience.", "kind": "supported_claim", "evidence_ids": ["profile:resume"]}
    positive["skills_required_knowledge"] = [claim]
    single = judge_case(case(), positive, negative)
    positive["skills_required_knowledge"] = [claim] * 5
    repeated = judge_case(case(), positive, negative)
    assert single["match_score"] == repeated["match_score"]
    positive["skills_required_knowledge"] = [{**claim, "kind": "artifact_evidence", "evidence_ids": ["depth:e:E1"]}]
    artifact = judge_case(case(), positive, negative)
    assert artifact["match_score"] > single["match_score"]


def test_no_full_job_description_means_no_numeric_score():
    inputs = case()
    inputs["job"]["description_status"] = "listing_only"
    result = judge_case(inputs, empty(), empty())
    assert result["match_score"] is None
    assert result["verdict"] == "needs_job_description"


def test_no_supported_requirements_is_honestly_low():
    result = judge_case(case(), empty(), empty())
    assert result["match_score"] == 0
    assert result["verdict"] == "limited_documented_match"


def test_unrelated_project_strength_does_not_inflate_job_match():
    positive = empty()
    positive["projects"] = [{"text": "The FPGA project has inspected tests.",
                             "kind": "artifact_evidence", "evidence_ids": ["depth:e:E1"]}]
    result = judge_case(case(), positive, empty())
    assert result["match_score"] == 0
    assert result["score_breakdown"]["cited_support_quality"] == 0


def test_cited_gap_reduces_coverage_but_unknown_only_changes_explanation():
    positive, negative = empty(), empty()
    positive["skills_required_knowledge"] = [{"text": "Python is demonstrated in this project.",
                                                "kind": "artifact_evidence", "evidence_ids": ["depth:e:E1"]}]
    baseline = judge_case(case(), positive, negative)
    negative["skills_required_knowledge"] = [{"text": "Python verification is unknown.", "kind": "unknown", "evidence_ids": []}]
    assert judge_case(case(), positive, negative)["match_score"] == baseline["match_score"]
    negative["skills_required_knowledge"] = [{"text": "Python requirement is contradicted by the candidate record.",
                                                "kind": "gap", "evidence_ids": ["profile:resume"]}]
    assert judge_case(case(), positive, negative)["match_score"] == baseline["match_score"]
    inputs = case()
    inputs["evidence"][1]["excerpt"] = "No Python experience"
    assert judge_case(inputs, positive, negative)["match_score"] < baseline["match_score"]


def test_gemini_lawyer_provider_uses_same_validated_case(monkeypatch):
    from backend.web import gemini_lawyer

    calls = []
    def fake_generate(system, content, schema, **kwargs):
        calls.append((system, content, schema, kwargs))
        result = empty()
        if "positive Lawyer" in system:
            result["projects"] = [{"text": "The Python project has a tested endpoint.",
                                   "kind": "artifact_evidence", "evidence_ids": ["depth:e:E1"]}]
        return result

    monkeypatch.setattr(gemini_lawyer, "generate_json", fake_generate)
    monkeypatch.setenv("LAWYER_PROVIDER", "gemini")
    inputs = {**case(), "depth_projects": []}
    result = review.run_review(inputs)
    assert result["provider"] == "gemini"
    assert result["judge"]["match_score"] == 52
    assert len(calls) == 2
    assert all(call[1]["positive_review"] is None for call in calls)
    assert result["lawyer_execution"] == "independent_parallel"


def test_lawyers_start_independently_before_either_finishes(monkeypatch):
    from threading import Barrier

    started = Barrier(2, timeout=3)
    def fake_lawyer(model, role, requirements, evidence, depth_projects, positive_review=None):
        assert positive_review is None
        started.wait()
        return empty()

    monkeypatch.setenv("LAWYER_PROVIDER", "ollama")
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    result = review.run_review({**case(), "depth_projects": []})
    assert result["lawyer_execution"] == "independent_parallel"


def test_lawyer_model_failure_keeps_direct_score_and_reports_degraded_review(monkeypatch):
    inputs = {
        "job": {"source": "simplify", "description_status": "fetched", "requirements_status": "source_checked"},
        "requirements": [{"id": "required:1", "kind": "required", "text": "Python", "alternatives": [], "source_quote": "Python"}],
        "evidence": [{"id": "profile:resume", "source": "resume_claim", "excerpt": "Built a Python API"}],
        "depth_projects": [],
    }
    def fake_lawyer(_model, role, *_args):
        if role == "negative":
            raise RuntimeError("Gemini request failed with HTTP 503")
        return empty()
    monkeypatch.setenv("LAWYER_PROVIDER", "ollama")
    monkeypatch.setattr(review.lawyers, "review_with_ollama", fake_lawyer)
    result = review.run_review(inputs)
    assert result["judge"]["match_score"] == 50
    assert result["lawyer_execution"] == "partial_model_failure"
    assert "negative" in result["lawyer_errors"]


def test_source_checked_score_respects_or_groups_and_ignores_irrelevant_repos():
    inputs = {
        "job": {"source": "simplify", "description_status": "fetched", "requirements_status": "source_checked"},
        "requirements": [
            {"id": "required:1", "kind": "required", "text": "Experience in VHDL, Verilog, or SystemVerilog", "alternatives": ["VHDL", "Verilog", "SystemVerilog"], "source_quote": "Experience in VHDL, Verilog, or SystemVerilog"},
            {"id": "required:2", "kind": "required", "text": "Proficient in C, C++, or Python", "alternatives": ["C", "C++", "Python"], "source_quote": "Proficient in C, C++, or Python"},
            {"id": "preferred:1", "kind": "preferred", "text": "Previous industry experience with FPGAs", "alternatives": [], "source_quote": "Previous industry experience with FPGAs"},
            {"id": "eligibility:1", "kind": "eligibility", "text": "Graduation in 2028", "alternatives": [], "source_quote": "Graduation in 2028"},
        ],
        "evidence": [
            {"id": "depth:e:1", "source": "depth_repository", "excerpt": "module device"},
            {"id": "profile:skill:1", "source": "resume_claim", "excerpt": "Python, self-rated 3/5"},
        ],
        "depth_projects": [{"project_id": "one", "demonstrated_skills": [{"skill": "SystemVerilog RTL Design", "evidence_ids": ["depth:e:1"]}]}],
    }
    result = judge_case(inputs, empty(), empty())
    assert result["match_score"] == 60
    assert result["eligibility"] == "unknown"
    assert [item["status"] for item in result["requirements"]] == ["inspected artifact", "candidate claim", "not_shown"]
    inputs["depth_projects"].append({"project_id": "unrelated", "demonstrated_skills": [{"skill": "React", "evidence_ids": ["depth:e:1"]}]})
    assert judge_case(inputs, empty(), empty())["match_score"] == result["match_score"]
    invented = empty()
    invented["projects"] = [{"text": "Industry FPGA experience was demonstrated.", "kind": "artifact_evidence", "evidence_ids": ["depth:e:1"]}]
    assert judge_case(inputs, invented, empty())["match_score"] == result["match_score"]


def test_simplify_without_source_checked_qualifications_abstains():
    inputs = {**case(), "job": {"source": "simplify", "description_status": "fetched", "requirements_status": "unavailable"}}
    result = judge_case(inputs, empty(), empty())
    assert result["match_score"] is None
    assert result["verdict"] == "needs_verified_requirements"


def test_source_checked_claims_do_not_count_negated_or_planned_skills():
    inputs = {
        "job": {"source": "simplify", "description_status": "fetched", "requirements_status": "source_checked"},
        "requirements": [{"id": "required:1", "kind": "required", "text": "Python", "alternatives": [], "source_quote": "Python"}],
        "evidence": [{"id": "profile:resume", "source": "resume_claim", "excerpt": "No Python experience. Planned: Python course."}],
        "depth_projects": [],
    }
    assert judge_case(inputs, empty(), empty())["match_score"] == 0
    inputs["evidence"][0]["excerpt"] += " Built a Python API."
    assert judge_case(inputs, empty(), empty())["match_score"] == 50


def test_unverified_job_skips_lawyer_model_calls(monkeypatch):
    monkeypatch.setenv("LAWYER_PROVIDER", "gemini")
    monkeypatch.setattr(review, "review_with_gemini", lambda *_args: (_ for _ in ()).throw(AssertionError("Model called")))
    inputs = {**case(), "job": {"source": "simplify", "description_status": "fetched", "requirements_status": "unavailable"},
              "requirements": [], "depth_projects": []}
    result = review.run_review(inputs)
    assert result["lawyer_execution"] == "skipped_unverified_requirements"
    assert result["judge"]["match_score"] is None
