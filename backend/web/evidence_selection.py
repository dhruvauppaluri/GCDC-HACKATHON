"""Bound the Lawyer prompt while retaining every project's cited findings."""
from collections import defaultdict
import re


STOP = {"about", "after", "and", "are", "for", "from", "have", "into", "other", "such",
        "that", "the", "their", "this", "through", "with", "work", "experience", "skills"}


def _tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9+#]+", text.casefold()) if len(word) >= 3 and word not in STOP}


def select_lawyer_evidence(bundle: dict, requirements: list[dict], evidence: list[dict],
                           depth_projects: list[dict], extras_per_project: int = 4) -> list[dict]:
    """Keep cited assessment anchors and a few relevant uncited excerpts per repo."""
    anchors = set()
    for project in depth_projects:
        for value in project.get("dimensions", {}).values():
            anchors.update(value.get("evidence_ids", []))
        for skill in project.get("demonstrated_skills", []):
            anchors.update(skill.get("evidence_ids", []))
    for assessment in bundle.get("project_assessments", []):
        result = assessment.get("result") or {}
        evaluation_id = assessment.get("evaluation_id")
        if evaluation_id:
            for field in ("summary_evidence_ids", "architecture_evidence_ids"):
                anchors.update(f"depth:{evaluation_id}:{item}" for item in result.get(field, []))

    query = _tokens(bundle["job"].get("title", "") + " " + " ".join(
        item["text"] for item in requirements if item.get("kind") in {"required", "preferred"}))
    by_project = defaultdict(list)
    for item in evidence:
        if item["source"].startswith("depth_"):
            by_project[item.get("project_id")].append(item)
    keep = set(anchors)
    for items in by_project.values():
        extras = [item for item in items if item["id"] not in keep]
        extras.sort(key=lambda item: (-len(_tokens(item.get("excerpt", "")) & query), item["id"]))
        relevant = [item for item in extras if _tokens(item.get("excerpt", "")) & query]
        keep.update(item["id"] for item in relevant[:extras_per_project])
        if not any(item["id"] in keep for item in items) and extras:
            keep.add(extras[0]["id"])
    return [item for item in evidence if not item["source"].startswith("depth_") or item["id"] in keep]
