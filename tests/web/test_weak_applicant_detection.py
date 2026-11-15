"""A weak application must not gain credit by naming absent skills."""
import pytest

from backend.web.judge import affirmative_mention, judge_case
from backend.web.review import _filter_unmatched_claim_strengths, review_inputs


CASES = [
    ("software", "Learning Python. No API or SQL project. Built a static HTML portfolio.",
     ["Python", "REST API", "SQL", "automated testing"], 0),
    ("software", "Built a Python log parser and tested malformed records with pytest. No REST API or SQL work yet.",
     ["Python", "REST API", "SQL", "automated testing"], 25),
    ("product", "Have not conducted user research or used product metrics. No roadmap ownership.",
     ["user research", "product prioritization", "product metrics", "stakeholder coordination"], 0),
    ("product", "Ran five user interviews for a campus shuttle idea. Have not set product metrics or prioritized a roadmap.",
     ["user research", "product prioritization", "product metrics", "stakeholder coordination"], 12),
    ("hardware", "Learning SystemVerilog and FPGA design. No testbench simulation or timing analysis.",
     ["SystemVerilog", "FPGA design", "testbench simulation", "timing analysis"], 0),
    ("hardware", "Wrote a SystemVerilog counter and ran testbench simulation. Did not build an FPGA design or perform timing analysis.",
     ["SystemVerilog", "FPGA design", "testbench simulation", "timing analysis"], 25),
]


def case_bundle(track, resume, required):
    requirements = [
        {"id": f"required:{index}", "kind": "required", "text": text, "source_quote": text, "alternatives": []}
        for index, text in enumerate(required, 1)
    ]
    return {
        "schema_version": 1,
        "case_id": f"weak-{track}",
        "candidate": {"candidate_id": f"weak-{track}", "resume_text": resume, "skills": {}, "projects": []},
        "job": {"job_id": f"job-{track}", "track": track, "title": f"{track} internship",
                "company": "Synthetic Test", "source": "pasted", "description_status": "full",
                "requirements_status": "source_checked", "requirement_groups": requirements,
                "description": "Required: " + ", ".join(required)},
        "project_assessments": [],
    }


@pytest.mark.parametrize("track,resume,required,expected_score", CASES)
def test_weak_application_score_uses_positive_claims_only(track, resume, required, expected_score):
    inputs = review_inputs(case_bundle(track, resume, required))
    empty = {category: [] for category in ("projects", "work_experience", "skills_required_knowledge")}
    result = judge_case(inputs, empty, empty)
    assert result["match_score"] == expected_score
    assert all(any(affirmative_mention(term, item["quote"]) for term in item["terms"])
               for item in inputs["paralegal"]["evidence"])
    if track == "product" and expected_score > 0:
        assert "user research" in {item["signal"] for item in inputs["paralegal"]["evidence"]}


def test_negation_does_not_cross_a_contrast_or_cancel_not_only():
    assert not affirmative_mention("SQL", "No SQL, but built a Python parser")
    assert affirmative_mention("Python", "No SQL, but built a Python parser")
    assert affirmative_mention("Python", "Used not only Python but also SQL")
    assert affirmative_mention("SQL", "Used not only Python but also SQL")


def test_advocate_cannot_use_learning_as_a_qualification():
    required = ["Python", "SQL"]
    weak = review_inputs(case_bundle("software", "Learning Python. No SQL experience.", required))
    partial = review_inputs(case_bundle("software", "Built a Python parser. No SQL experience.", required))
    point = {"text": "The candidate knows Python.", "kind": "supported_claim", "evidence_ids": ["profile:resume"]}
    review = {"projects": [], "work_experience": [], "skills_required_knowledge": [point]}
    assert _filter_unmatched_claim_strengths(weak, review)["skills_required_knowledge"] == []
    assert _filter_unmatched_claim_strengths(partial, review)["skills_required_knowledge"] == [point]
