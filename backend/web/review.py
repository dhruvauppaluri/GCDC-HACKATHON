"""Local trial adapter for Rishi's claim extractor and Harsh's two Lawyers."""
import os
import json
from pathlib import Path
import re
from concurrent.futures import ThreadPoolExecutor

from data.fixtures.rishi.swe_paralegal import extract
from prototypes.harsh.lawyers import lawyers
from .jobs import SKILL_OPTIONS
from .judge import judge_case
from .gemini_lawyer import review_with_gemini
from .evidence_selection import select_lawyer_evidence


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
        if result.get("evaluation_mode") in {"ollama", "gemini"}:
            depth_modes.append(result["evaluation_mode"])
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
        resume_text = candidate.get("resume_text", "")
        signals = []
        for skill in SKILL_OPTIONS.get(track, []):
            found = re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", resume_text, re.I)
            if found:
                start, end = max(0, found.start() - 90), min(len(resume_text), found.end() + 90)
                quote = ("…" if start else "") + resume_text[start:end].strip() + ("…" if end < len(resume_text) else "")
                signals.append({"signal": skill, "terms": [skill], "field": "resume", "quote": quote})
        paralegal = {"id": candidate["candidate_id"], "source": "local_track_terms", "evidence": signals}
    if paralegal:
        for index, item in enumerate(paralegal["evidence"], 1):
            evidence.append({
                "id": f"paralegal:{index}", "source": "resume_claim",
                "location": item["field"], "excerpt": item["quote"],
                "signal": item["signal"], "terms": item["terms"],
            })
    requirements = (job.get("requirement_groups", []) if job.get("source") in {"simplify", "pasted"}
                    else lawyers.job_requirements(job))
    evidence = select_lawyer_evidence(bundle, requirements, evidence, depth_projects)
    return {
        "case_id": bundle["case_id"], "candidate_id": candidate["candidate_id"],
        "job_id": job["job_id"], "job": job,
        "requirements": requirements,
        "evidence": evidence, "depth_projects": depth_projects,
        "paralegal": paralegal, "synthetic_comparisons": comparisons,
        "actual_depth_modes": depth_modes,
    }


def run_review(inputs: dict) -> dict:
    provider = os.getenv("LAWYER_PROVIDER", "ollama").casefold()
    if provider not in {"ollama", "gemini"}:
        raise ValueError("LAWYER_PROVIDER must be ollama or gemini")
    model = os.getenv("LAWYER_GEMINI_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")) if provider == "gemini" else os.getenv("LAWYER_OLLAMA_MODEL", "qwen3:4b")
    requirements, evidence, depth_projects = (inputs[key] for key in ("requirements", "evidence", "depth_projects"))
    if inputs["job"].get("source") in {"simplify", "pasted"} and inputs["job"].get("requirements_status") != "source_checked":
        empty = {category: [] for category in lawyers.CATEGORIES}
        return {"provider": provider, "model": model, "lawyer_execution": "skipped_unverified_requirements",
                "lawyers": {"positive": empty, "negative": empty},
                "categories": {category: {"pluses": [], "minuses": []} for category in lawyers.CATEGORIES},
                "judge": judge_case(inputs, empty, empty)}
    review_lawyer = (lambda role, previous=None: review_with_gemini(role, requirements, evidence, depth_projects, previous)) if provider == "gemini" else (lambda role, previous=None: lawyers.review_with_ollama(model, role, requirements, evidence, depth_projects, previous))
    # Both model calls receive the same frozen case and neither sees the
    # other's argument. Reconcile contradictions only after both finish.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="lawyer") as pool:
        positive_future = pool.submit(review_lawyer, "positive")
        negative_future = pool.submit(review_lawyer, "negative")
        empty = {category: [] for category in lawyers.CATEGORIES}
        errors = {}
        try:
            positive = positive_future.result()
        except Exception as error:
            positive = empty
            errors["positive"] = str(error)
        try:
            independent_negative = negative_future.result()
        except Exception as error:
            independent_negative = empty
            errors["negative"] = str(error)
    negative = lawyers.clean_negative(
        independent_negative,
        positive, requirements,
    )
    return {
        "provider": provider, "model": model,
        "lawyer_execution": "independent_parallel" if not errors else "partial_model_failure" if len(errors) == 1 else "model_unavailable",
        "lawyer_errors": errors,
        "lawyers": {"positive": positive, "negative": negative},
        "categories": {category: {"pluses": positive[category], "minuses": negative[category]} for category in lawyers.CATEGORIES},
        "judge": judge_case(inputs, positive, negative),
    }
