"""Semantic matcher, paralegal v2 and metamorphic stability checks (no network)."""
import itertools

import pytest

from backend.web import matching, ontology, paralegal
from backend.web.judge import judge_case
from backend.web import review


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("MATCH_CACHE_PATH", str(tmp_path / "match.sqlite3"))
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_2", "MATCHER", "PARALEGAL"):
        monkeypatch.delenv(name, raising=False)


def req(text, kind="required", **extra):
    return {"id": f"{kind}:{text[:6]}", "kind": kind, "text": text, "alternatives": [], **extra}


def claim(id_, text):
    return {"id": id_, "source": "resume_claim", "excerpt": text}


def artifact(id_, text):
    return {"id": id_, "source": "depth_repository", "excerpt": text}


def test_ontology_links_equivalent_wording_across_tracks():
    assert "experimentation" in ontology.concepts_in("Ran an A/B test on the signup page")
    assert "user research" in ontology.concepts_in("Conducted customer interviews with 12 users")
    assert "hardware verification" in ontology.concepts_in("Wrote a scoreboard and golden model")
    assert "systemverilog" in ontology.related_to({"verilog"})
    assert not ontology.concepts_in("Enjoys hiking and chess")


def test_equivalent_experience_is_found_without_the_exact_term():
    evidence = [claim("c1", "Ran customer interviews with twelve campus club leaders and synthesized the pain points")]
    result = matching.assess_requirement(req("Experience with user research"), evidence)
    assert result["evidence_ids"] == ["c1"] and result["coverage"] > 0.5


def test_planned_or_negated_skill_gets_no_credit():
    for text in ("Learning SQL this semester", "No SQL experience yet, hope to use it for analytics"):
        assert matching.assess_requirement(req("SQL"), [claim("c1", text)])["coverage"] == 0.0


def test_unquoted_model_verdict_is_void(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(matching, "_embed", lambda texts: None)
    import backend.web.gemini_client as client
    monkeypatch.setattr(client, "generate_json", lambda *a, **k: {"assessments": [
        {"evidence_id": "c1", "relationship": "direct", "specific": True, "negated_or_planned": False,
         "quote": "led a team of fifty engineers"}]})
    result = matching.assess_requirement(req("Leadership of engineers"), [claim("c1", "Member of the chess club for two years")])
    assert result["coverage"] == 0.0


def test_verified_results_are_cached_so_reruns_are_identical(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(matching, "_embed", lambda texts: None)
    calls = []
    import backend.web.gemini_client as client

    def fake(system, payload, schema, **kwargs):
        calls.append(1)
        return {"assessments": [{"evidence_id": "c1", "relationship": "direct", "specific": True,
                                 "negated_or_planned": False, "quote": "built a Python parser"}]}

    monkeypatch.setattr(client, "generate_json", fake)
    evidence = [claim("c1", "I built a Python parser for log files")]
    first = matching.assess_requirement(req("Python"), evidence)
    second = matching.assess_requirement(req("Python"), evidence)
    assert first == second and len(calls) == 1


def test_depth_asked_for_limits_credit_for_early_career_applicants():
    generic = [claim("c1", "Used SQL in a database course project")]
    familiar = matching.assess_requirement(req("SQL", expected_depth="familiarity"), generic)
    working = matching.assess_requirement(req("SQL", expected_depth="working"), generic)
    advanced = matching.assess_requirement(req("SQL", expected_depth="advanced"), generic)
    assert familiar["coverage"] == 1.0 > working["coverage"] > advanced["coverage"] > 0


def test_artifact_outranks_claim_and_related_is_partial():
    direct = matching.assess_requirement(req("Python", expected_depth="advanced"), [artifact("a1", "def main(): print('Python service')")])
    claimed = matching.assess_requirement(req("Python", expected_depth="advanced"), [claim("c1", "Used Python in a class project to build a game")])
    assert direct["coverage"] > claimed["coverage"]
    related = matching.assess_requirement(req("SystemVerilog", expected_depth="working"), [artifact("a1", "module fifo; // Verilog design")])
    assert 0 < related["coverage"] < 1 and related["status"] == "transferable artifact"


# ---- metamorphic properties of the whole score -------------------------------------------------
def case(evidence, requirements=None):
    return {"job": {"description_status": "full", "requirements_status": "source_checked", "source": "pasted",
                    "eligibility_requirements": []},
            "requirements": requirements or [req("Python"), req("SQL"), req("A/B testing", kind="preferred")],
            "evidence": evidence, "full_evidence": evidence}


def empty():
    return {category: [] for category in review.lawyers.CATEGORIES}


def score(evidence, requirements=None):
    return judge_case(case(evidence, requirements), empty(), empty())["match_score"]


BASE = [artifact("a1", "def handler(): # Python API service"), claim("c1", "Wrote SQL queries to build a retention dashboard"),
        claim("c2", "Ran an A/B test on the onboarding flow")]


def test_order_duplicates_and_irrelevant_evidence_do_not_change_the_score(monkeypatch):
    monkeypatch.setenv("MATCHER", "semantic")
    base = score(BASE)
    assert {score(list(p)) for p in itertools.permutations(BASE)} == {base}
    assert score(BASE + BASE) == base or score(BASE + [{**e, "id": e["id"] + "x"} for e in BASE]) == base
    noise = [artifact(f"n{i}", "README: Shopping list app with dark mode") for i in range(20)]
    assert score(BASE + noise) == base


def test_removing_support_lowers_and_adding_support_never_lowers(monkeypatch):
    monkeypatch.setenv("MATCHER", "semantic")
    base = score(BASE)
    assert score(BASE[:2]) < base and score(BASE[:1]) < score(BASE[:2])
    assert score(BASE + [artifact("a2", "SELECT * FROM events; -- SQL analytics warehouse")]) >= base


def test_score_range_is_reported_and_bounded(monkeypatch):
    monkeypatch.setenv("MATCHER", "semantic")
    result = judge_case(case(BASE), empty(), empty())
    assert result["score_breakdown"]["method"] == "semantic_verified_graded"
    assert 0 <= result["score_range"]["low"] <= result["match_score"] <= 100


def test_preferred_gaps_cost_less_than_required_gaps(monkeypatch):
    monkeypatch.setenv("MATCHER", "semantic")
    evidence = [artifact("a1", "def handler(): # Python API service")]
    missing_preferred = score(evidence, [req("Python"), req("Rust", kind="preferred")])
    missing_required = score(evidence, [req("Python", kind="preferred"), req("Rust")])
    assert missing_preferred > missing_required


# ---- paralegal v2 ------------------------------------------------------------------------------
def test_paralegal_drops_invented_spans_and_unsupported_facts():
    text = "Education: B.A. Economics. Interviewed student users and wrote a product brief. Learning SQL."
    raw = {"claims": [
        {"span": "Interviewed student users and wrote a product brief.", "section": "experience", "skills": ["user research"],
         "terms": ["Interviewed", "not in text"], "specific": True, "has_outcome": False, "ownership": "individual", "negated_or_planned": False},
        {"span": "Led a 40 person engineering team at Google", "section": "experience", "skills": ["leadership"],
         "terms": ["Led"], "specific": True, "has_outcome": False, "ownership": "individual", "negated_or_planned": False},
        {"span": "Learning SQL.", "section": "skills_list", "skills": ["sql"], "terms": ["SQL"], "specific": False,
         "has_outcome": False, "ownership": "unclear", "negated_or_planned": True}],
        "facts": [{"field": "degree", "value": "B.A. Economics", "span": "B.A. Economics"},
                  {"field": "work_authorization", "value": "US citizen", "span": "US citizen"}]}
    result = paralegal._validate(raw, text)
    assert [c["span"] for c in result["claims"]] == ["Interviewed student users and wrote a product brief."]
    assert result["claims"][0]["terms"] == ["Interviewed"]
    assert "user research" in result["claims"][0]["skills"]
    assert [f["field"] for f in result["facts"]] == ["degree"]


def test_paralegal_falls_back_when_unavailable():
    assert paralegal.extract("Interviewed users and wrote a product brief for a campus app.") is None


def test_bare_skills_list_earns_less_than_the_same_skill_shown_in_coursework():
    listed = matching.assess_requirement(req("SQL", expected_depth="working"), [claim("c1", "Skills: SQL, Python, Git")])
    coursework = matching.assess_requirement(req("SQL", expected_depth="working"), [claim("c1", "Used SQL in a database course project")])
    assert 0 < listed["coverage"] < coursework["coverage"]


def test_skills_and_coursework_lines_are_always_extracted_even_if_the_model_omits_them():
    text = "Education: B.S. CS\nRelevant coursework: algorithms, operating systems\nSkills: Python, SQL, Git\n"
    claims = paralegal._list_claims(text)
    assert [c["section"] for c in claims] == ["coursework", "skills_list"]
    assert paralegal._validate({"claims": claims, "facts": []}, text)["claims"][1]["terms"] == ["Python", "SQL", "Git"]
