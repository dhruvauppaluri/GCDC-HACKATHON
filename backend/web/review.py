"""Local trial adapter for Rishi's claim extractor and Harsh's two Lawyers."""
import os
import json
from pathlib import Path
import re

from data.fixtures.rishi.lawyers_grounded import verify_findings
from prototypes.harsh.lawyers import lawyers
from .jobs import skill_alternatives
from .paralegal import extract_facts
from .judge import rate as rate_evidence


def synthetic_comparisons(signals: set[str]) -> list[dict]:
    """Find illustrative SWE examples; simulated outcomes are intentionally excluded."""
    path = Path(__file__).resolve().parents[2] / "data/fixtures/rishi/swe-applications.json"
    pool = json.loads(path.read_text())
    ranked = []
    for record in pool["applications"]:
        report = extract(record)
        overlap = sorted(signals & {item["signal"] for item in report["evidence"]})
        if overlap:
            ranked.append({"application_id": record["id"], "shared_claim_signals": overlap,
                           "example_project": report["projects"][0] if report["projects"] else ""})
    ranked.sort(key=lambda item: (-len(item["shared_claim_signals"]), item["application_id"]))
    return ranked[:3]


def review_inputs(bundle: dict) -> dict:
    # Harsh's prototype recognizes live/codex results. Ollama is a real local
    # evaluation in this trial, so adapt its mode only in the prototype input.
    lawyer_bundle = json.loads(json.dumps(bundle))
    depth_modes = []
    for assessment in lawyer_bundle.get("project_assessments", []):
        result = assessment.get("result") or {}
        if result.get("evaluation_mode") == "ollama":
            depth_modes.append("ollama")
            result["evaluation_mode"] = "live"
        elif result.get("evaluation_mode"):
            depth_modes.append(result["evaluation_mode"])
    candidate, job, evidence, depth_projects = lawyers.case_inputs(lawyer_bundle)
    paralegal = {"source": "pending_model_extraction", "evidence": []}
    return {
        "case_id": bundle["case_id"], "candidate_id": candidate["candidate_id"],
        "job_id": job["job_id"], "job": job,
        "requirements": lawyers.job_requirements(job),
        "evidence": evidence, "depth_projects": depth_projects,
        "paralegal": paralegal, "synthetic_comparisons": [],
        "actual_depth_modes": depth_modes,
    }


def trial_judge(inputs: dict, positive: dict, negative: dict) -> dict:
    """Conservative local integration placeholder until the shared Judge exists."""
    categories = lawyers.CATEGORIES
    strengths = [point for category in categories for point in positive[category] if point["kind"] != "unknown"]
    objections = [point for category in categories for point in negative[category] if point["kind"] != "unknown"]
    confirmed_gaps = [point for point in objections if point["kind"] == "gap"]
    verified_projects = any(project.get("dimensions") for project in inputs["depth_projects"])
    evidence = {item["id"]: item for item in inputs["evidence"]}
    rating = rate_evidence(inputs.get("requirements") or lawyers.job_requirements(inputs["job"]),
                           positive, negative, inputs["evidence"], _mentions_skill)
    requirement_support = []
    for requirement in inputs["job"].get("required_skills", []):
        supporting = []
        for point in strengths:
            for citation in point["evidence_ids"]:
                item = evidence.get(citation)
                if not item or item["source"] not in {"depth_repository", "depth_document"}:
                    continue
                if any(_mentions_skill(point["text"], option) and _mentions_skill(item["excerpt"], option)
                       for option in skill_alternatives(str(requirement))):
                    supporting.append(citation)
        requirement_support.append({"requirement": str(requirement),
                                    "status": "artifact_supported" if supporting else "unknown",
                                    "evidence_ids": list(dict.fromkeys(supporting))})
    if inputs["job"].get("description_status") == "listing_only":
        verdict = "needs_job_description"
    else:
        verdict = "review_required" if confirmed_gaps else "promising_match" if requirement_support and all(
            item["status"] == "artifact_supported" for item in requirement_support
        ) and strengths and verified_projects else "needs_more_evidence"
    return {
        "version": "local-trial-v1", "verdict": verdict,
        "eligibility": "unknown" if inputs["job"].get("eligibility_requirements") else "not_specified",
        "strengths": strengths, "objections": objections, "required_skill_evidence": requirement_support,
        "evidence_rating": rating,
        "confidence": "medium" if verdict == "promising_match" else "low",
        "note": "Provisional integration summary. The jointly owned Judge is not implemented or calibrated yet; this is not a hiring decision.",
    }


def _mentions_skill(text: str, skill: str) -> bool:
    """Require a literal skill mention; uncertain synonyms remain unknown."""
    forms = {skill.casefold()}
    if skill.casefold() == "testing":
        forms.add("test")
    if skill.casefold() == "apis":
        forms.add("api")
    return any(re.search(r"(?<!\w)" + re.escape(form) + r"(?:s|ed|ing)?(?!\w)", text, re.I)
               for form in forms)


def _keep_category_evidence(review: dict, evidence: list[dict]) -> dict:
    """Keep project and employment findings within their cited source categories."""
    sources = {item["id"]: item for item in evidence}
    review["projects"] = [point for point in review["projects"]
                          if point["kind"] == "unknown" or any(
                              sources[key]["source"] in {"depth_repository", "depth_document"} or
                              sources[key]["location"].startswith("project/") or
                              sources[key].get("category") == "project"
                              for key in point["evidence_ids"] if key in sources)]
    review["work_experience"] = [point for point in review["work_experience"]
                                 if point["evidence_ids"] and not any(
                                     key.startswith("depth:") or key.startswith("profile:project:") or
                                      sources[key]["location"].startswith("project/") or
                                      sources[key].get("category") != "work_experience"
                                     for key in point["evidence_ids"] if key in sources)]
    return review


def _ground_required_skill_claims(review: dict, requirements: list[dict], evidence: list[dict]) -> dict:
    """A model verifier cannot make a cited Java excerpt support SQL."""
    excerpts = {item["id"]: item["excerpt"] for item in evidence}
    required = [skill_alternatives(item["text"]) for item in requirements if item["kind"] == "required"]
    for points in review.values():
        for point in points:
            if point["kind"] == "unknown":
                continue
            for options in required:
                mentioned = [option for option in options if _mentions_skill(point["text"], option)]
                if mentioned and not any(_mentions_skill(excerpts.get(key, ""), option)
                                         for key in point["evidence_ids"] for option in mentioned):
                    point.update(kind="unknown", text="The cited evidence does not support the required skill claim.")
                    break
    return review


def run_review(inputs: dict) -> dict:
    model = os.getenv("LAWYER_OLLAMA_MODEL", "qwen3:4b")
    source_evidence = inputs["evidence"]
    paralegal = extract_facts(source_evidence)
    inputs = {**inputs, "paralegal": paralegal}
    # The case retains full source excerpts; Lawyers see only extracted candidate spans
    # plus independent Depth evidence, preventing uncategorized résumé text being cited.
    inputs["evidence"] = [*(item for item in source_evidence if item["source"] != "resume_claim"), *(
        {"id": f"paralegal:{index}", "source": "resume_claim",
         "location": next(item["location"] for item in source_evidence if item["id"] == fact["source_id"]),
         "excerpt": fact["quote"], "source_id": fact["source_id"], "category": fact["category"]}
        for index, fact in enumerate(paralegal["evidence"], 1))]
    requirements, evidence, depth_projects = (inputs[key] for key in ("requirements", "evidence", "depth_projects"))
    positive = _keep_category_evidence(_ground_required_skill_claims(verify_findings(model,
        lawyers.review_with_ollama(model, "positive", requirements, evidence, depth_projects),
        requirements, evidence), requirements, evidence), evidence)
    negative = lawyers.clean_negative(
        verify_findings(model,
            lawyers.review_with_ollama(model, "negative", requirements, evidence, depth_projects, positive),
            requirements, evidence),
        positive, requirements,
    )
    positive = {category: [point for point in points if point["kind"] != "unknown"]
                for category, points in positive.items()}
    negative = {category: [point for point in points if point["kind"] != "unknown"]
                for category, points in negative.items()}
    judge = trial_judge(inputs, positive, negative)
    negative["skills_required_knowledge"].extend(
        {"text": f"No cited evidence establishes {row['requirement']}; this requirement remains unknown.",
         "evidence_ids": [], "kind": "unknown"}
        for row in judge["evidence_rating"]["requirements"]
        if row["kind"] == "required" and row["status"] == "unknown"
    )
    return {
        "model": model, "paralegal": paralegal, "lawyers": {"positive": positive, "negative": negative},
        "categories": {category: {"pluses": positive[category], "minuses": negative[category]} for category in lawyers.CATEGORIES},
        "judge": judge,
    }
