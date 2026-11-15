"""Conservative, explainable evidence coverage rating for a specific role."""

from .jobs import skill_alternatives


def rate(requirements: list[dict], positive: dict, negative: dict, evidence: list[dict],
         mentions_skill) -> dict:
    """Score documented coverage; unknown requirements widen the range, not become failures."""
    by_id = {item["id"]: item for item in evidence}
    strengths = [point for points in positive.values() for point in points if point["kind"] != "unknown"]
    explicit_gaps = [point for points in negative.values() for point in points if point["kind"] == "gap"]
    rows = []
    for requirement in requirements:
        if requirement["kind"] not in {"required", "preferred"}:
            continue
        options = skill_alternatives(requirement["text"])
        artifact, claim, gap = [], [], []
        for point in strengths:
            for citation in point["evidence_ids"]:
                source = by_id.get(citation)
                if not source:
                    continue
                if any(mentions_skill(point["text"], option) and mentions_skill(source["excerpt"], option)
                       for option in options):
                    (artifact if source["source"] in {"depth_repository", "depth_document"} else claim).append(citation)
        # Structured self-ratings are explicit candidate claims even when the
        # advocate omits them. They never count as verified artifact evidence.
        if not artifact and not claim:
            for citation, source in by_id.items():
                if source.get("category") == "skill" and source.get("location", "").startswith("skills/") and any(
                    mentions_skill(source["excerpt"], option) for option in options
                ):
                    claim.append(citation)
        for point in explicit_gaps:
            if any(mentions_skill(point["text"], option) for option in options):
                gap.extend(citation for citation in point["evidence_ids"] if citation in by_id)
        status = "artifact_supported" if artifact else "claimed" if claim else "gap" if gap else "unknown"
        rows.append({"requirement_id": requirement["id"], "requirement": requirement["text"],
                     "kind": requirement["kind"], "status": status,
                     "evidence_ids": list(dict.fromkeys(artifact or claim or gap))})
    if not rows:
        return {"score": None, "score_range": None, "rating": "unassessed", "requirements": []}
    if all(row["status"] == "unknown" for row in rows):
        return {"score": None, "score_range": None, "rating": "unassessed", "requirements": rows,
                "method": "No cited evidence for any job requirement; a numeric rating would be misleading."}
    # Required requirements carry four times the weight of preferences.
    weights = [4 if row["kind"] == "required" else 1 for row in rows]
    denominator = sum(weights)
    values = {"artifact_supported": 1.0, "claimed": 0.5, "gap": 0.0, "unknown": 0.0}
    floor = round(100 * sum(weight * values[row["status"]] for weight, row in zip(weights, rows)) / denominator)
    unknown_weight = sum(weight for weight, row in zip(weights, rows) if row["status"] == "unknown")
    ceiling = round(100 * (sum(weight * values[row["status"]] for weight, row in zip(weights, rows)) + unknown_weight) / denominator)
    exact = floor if unknown_weight == 0 else None
    rating = "well_supported" if exact is not None and exact >= 75 else "partially_supported" if exact is not None else "insufficient_evidence"
    return {"score": exact, "score_range": [floor, ceiling], "rating": rating, "requirements": rows,
            "method": "Required requirements weight 4; preferred weight 1. Artifact support earns full credit, candidate claims half, explicit gaps zero, and unknowns widen the range."}
