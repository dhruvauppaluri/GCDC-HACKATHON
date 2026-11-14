"""Local trial adapter for Rishi's claim extractor and Harsh's two Lawyers."""
import os
import json
from pathlib import Path
import re

from data.fixtures.rishi.swe_paralegal import extract
from prototypes.harsh.lawyers import lawyers
from .jobs import SKILL_OPTIONS


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
    paralegal = None
    comparisons = []
    if job.get("track") == "software":
        project_claims = [
            text for assessment in bundle.get("project_assessments", [])
            for text in (assessment["project"].get("summary", ""), assessment["project"].get("contribution", ""))
            if text
        ]
        paralegal = extract({
            "id": candidate["candidate_id"], "company": job.get("company", ""),
            "role": job.get("title", ""),
            "application": {"education": "", "coursework": "", "projects": project_claims,
                            "prior_experience": [line.strip() for line in candidate.get("resume_text", "").splitlines() if line.strip()]},
        })
        paralegal["source"] = "rishi_swe_extractor"
        comparisons = synthetic_comparisons({item["signal"] for item in paralegal["evidence"]})
    else:
        track = {"hardware": "HW", "product": "PM"}.get(job.get("track"))
        lines = candidate.get("resume_text", "").splitlines()
        signals = []
        for skill in SKILL_OPTIONS.get(track, []):
            found = next((line.strip() for line in lines if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", line, re.I)), None)
            if found:
                signals.append({"signal": skill, "terms": [skill], "field": "resume", "quote": found})
        paralegal = {"id": candidate["candidate_id"], "source": "local_track_terms", "evidence": signals}
    if paralegal:
        for index, item in enumerate(paralegal["evidence"], 1):
            evidence.append({
                "id": f"paralegal:{index}", "source": "resume_claim",
                "location": item["field"], "excerpt": item["quote"],
                "signal": item["signal"], "terms": item["terms"],
            })
    return {
        "case_id": bundle["case_id"], "candidate_id": candidate["candidate_id"],
        "job_id": job["job_id"], "job": job,
        "requirements": lawyers.job_requirements(job),
        "evidence": evidence, "depth_projects": depth_projects,
        "paralegal": paralegal, "synthetic_comparisons": comparisons,
        "actual_depth_modes": depth_modes,
    }


def trial_judge(inputs: dict, positive: dict, negative: dict) -> dict:
    """Conservative local integration placeholder until the shared Judge exists."""
    categories = lawyers.CATEGORIES
    strengths = [point for category in categories for point in positive[category]]
    objections = [point for category in categories for point in negative[category]]
    confirmed_gaps = [point for point in objections if point["kind"] == "gap"]
    verified_projects = any(project.get("dimensions") for project in inputs["depth_projects"])
    if inputs["job"].get("description_status") == "listing_only":
        verdict = "needs_job_description"
    else:
        verdict = "review_required" if confirmed_gaps else "promising_match" if strengths and verified_projects else "needs_more_evidence"
    return {
        "version": "local-trial-v1", "verdict": verdict,
        "eligibility": "unknown" if inputs["job"].get("eligibility_requirements") else "not_specified",
        "strengths": strengths, "objections": objections,
        "confidence": "medium" if verified_projects and strengths else "low",
        "note": "Provisional integration summary. The jointly owned Judge is not implemented or calibrated yet; this is not a hiring decision.",
    }


def run_review(inputs: dict) -> dict:
    model = os.getenv("LAWYER_OLLAMA_MODEL", "qwen3:4b")
    requirements, evidence, depth_projects = (inputs[key] for key in ("requirements", "evidence", "depth_projects"))
    positive = lawyers.review_with_ollama(model, "positive", requirements, evidence, depth_projects)
    negative = lawyers.clean_negative(
        lawyers.review_with_ollama(model, "negative", requirements, evidence, depth_projects, positive),
        positive, requirements,
    )
    return {
        "model": model, "lawyers": {"positive": positive, "negative": negative},
        "categories": {category: {"pluses": positive[category], "minuses": negative[category]} for category in lawyers.CATEGORIES},
        "judge": trial_judge(inputs, positive, negative),
    }
