"""Evidence-weighted, reproducible local Judge for candidate feedback.

The score describes how well the supplied application *documents* a match.
It must not be interpreted as a prediction of hiring or of a person's ability.
"""
import re

from prototypes.harsh.lawyers.lawyers import CATEGORIES


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    return {word[:-1] if word.endswith("s") and len(word) > 3 else word for word in words}


def _addresses(point: dict, requirement: dict) -> bool:
    terms = _tokens(requirement["text"])
    return bool(terms) and terms <= _tokens(point["text"])


def _merit(point: dict, citations: dict) -> dict:
    sources = sorted({citations[key]["source"] for key in point.get("evidence_ids", []) if key in citations})
    artifact = any(source in {"depth_repository", "depth_document"} for source in sources)
    if point["kind"] == "artifact_evidence" and artifact:
        weight, label = 1.0, "inspected artifact"
    elif point["kind"] == "supported_claim" and sources:
        weight, label = 0.5, "candidate claim"
    elif point["kind"] == "gap" and sources:
        weight, label = 0.0, "asserted gap"
    else:
        weight, label = 0.0, "unknown"
    return {**point, "merit": label, "weight": weight, "sources": sources}


def _explicit_gap(point: dict, requirement: dict, citations: dict) -> bool:
    """A skeptical assertion alone is not proof of a missing qualification."""
    if point["kind"] != "gap" or not _addresses(point, requirement):
        return False
    term = re.escape(requirement["text"])
    pattern = rf"\b(?:no|without|lacks?|not familiar with)\s+{term}\b"
    return any(re.search(pattern, citations[key].get("excerpt", ""), re.I)
               for key in point.get("evidence_ids", []) if key in citations)


def judge_case(inputs: dict, positive: dict, negative: dict) -> dict:
    """Weigh both arguments against explicit requirements and their citations."""
    citations = {item["id"]: item for item in inputs["evidence"]}
    pluses = [_merit(point, citations) for category in CATEGORIES for point in positive[category]]
    minuses = [_merit(point, citations) for category in CATEGORIES for point in negative[category]]
    requirements = [item for item in inputs["requirements"] if item["kind"] in {"required", "preferred"}]
    eligibility = "unknown" if inputs["job"].get("eligibility_requirements") else "not_specified"
    common = {
        "version": "local-trial-v2", "eligibility": eligibility,
        "strengths": pluses, "objections": minuses,
        "note": "Evidence-backed application feedback, not a hiring decision. A missing citation lowers documented match, not personal ability.",
    }
    if inputs["job"].get("description_status") == "listing_only":
        return {**common, "match_score": None, "verdict": "needs_job_description",
                "confidence": "low", "requirements": [], "score_breakdown": None}
    if not requirements:
        return {**common, "match_score": None, "verdict": "needs_parsed_requirements",
                "confidence": "low", "requirements": [], "score_breakdown": None}

    assessed = []
    total_weight = 0
    earned = 0.0
    for requirement in requirements:
        weight = 2 if requirement["kind"] == "required" else 1
        support = [point for point in pluses if point["weight"] and _addresses(point, requirement)]
        best = max(support, key=lambda point: point["weight"], default=None)
        gaps = [point for point in minuses if _explicit_gap(point, requirement, citations)]
        value = max(0.0, (best["weight"] if best else 0.0) - (0.25 if gaps else 0.0))
        total_weight += weight
        earned += value * weight
        assessed.append({"id": requirement["id"], "text": requirement["text"], "kind": requirement["kind"],
                         "status": "cited_gap" if gaps else best["merit"] if best else "not_shown",
                         "evidence_ids": best["evidence_ids"] if best else [], "coverage": value})
    requirement_score = round(100 * earned / total_weight)
    # A second, smaller component recognizes relevant cited project or work
    # evidence. Repeating many claims cannot inflate it.
    support_quality = max((point["weight"] for point in pluses if any(_addresses(point, requirement) for requirement in requirements)), default=0.0)
    score = round(0.8 * requirement_score + 20 * support_quality)
    if score >= 80:
        verdict = "strong_documented_match"
    elif score >= 60:
        verdict = "promising_documented_match"
    elif score >= 40:
        verdict = "partial_documented_match"
    else:
        verdict = "limited_documented_match"
    artifact_count = sum(point["merit"] == "inspected artifact" for point in pluses)
    confidence = "high" if artifact_count and all(item["coverage"] > 0 for item in assessed) else "medium" if artifact_count else "low"
    return {**common, "match_score": score, "verdict": verdict, "confidence": confidence,
            "requirements": assessed,
            "score_breakdown": {"requirement_coverage": requirement_score,
                                "cited_support_quality": round(100 * support_quality),
                                "weights": {"requirements": 0.8, "support_quality": 0.2}}}
