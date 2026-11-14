"""Candidate-owned handoff from selected projects to the Depth service."""
import os

import httpx


def depth_base() -> str:
    return os.getenv("DEPTH_API_URL", "http://127.0.0.1:8000").rstrip("/")


def start_depth(project: dict, track: str) -> str:
    data = {
        "project_id": project["id"],
        "career_track": track,
        "mode": os.getenv("DEPTH_INTEGRATION_MODE", "mock"),
    }
    if contribution := project.get("contribution"):
        data["project_text"] = contribution
    elif project["source"] == "resume":
        data["project_text"] = project["summary"]
    if project["source"] == "github":
        data["repository_url"] = project["url"]
    elif project["source"] == "website":
        data["website_url"] = project["url"]
    with httpx.Client(timeout=15) as client:
        response = client.post(f"{depth_base()}/depth/evaluations", data=data)
        response.raise_for_status()
        return response.json()["evaluation_id"]


def get_depth(evaluation_id: str) -> dict:
    with httpx.Client(timeout=15) as client:
        response = client.get(f"{depth_base()}/depth/evaluations/{evaluation_id}")
        response.raise_for_status()
        return response.json()


def hydrate_case(case: dict) -> dict:
    """Build one versioned, source-labeled bundle for both future lawyers."""
    assessments, citations = [], []
    for project in case["projects"]:
        if not project["evaluation_id"]:
            depth = {"status": "unavailable", "result": None, "error": project.get("start_error", "Depth evaluation was not started")}
        else:
            try:
                depth = get_depth(project["evaluation_id"])
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                depth = {"status": "unavailable", "result": None, "error": str(exc)}
        result = depth.get("result")
        assessment = {"project": project["project"], "evaluation_id": project["evaluation_id"], "status": depth["status"], "result": result, "error": depth.get("error")}
        assessments.append(assessment)
        if result:
            for item in result.get("evidence", []):
                citations.append({"ref": f"depth:{project['evaluation_id']}:{item['id']}", "project_id": project["project"]["id"], **item})
    statuses = {item["status"] for item in assessments}
    status = "pending" if statuses - {"complete", "failed", "unavailable"} else "complete" if statuses == {"complete"} else "partial"
    demonstrated = {item["skill"].casefold() for assessment in assessments if assessment["status"] == "complete" for item in assessment["result"].get("demonstrated_skills", [])}
    required = [str(skill) for skill in case["job"].get("required_skills", [])]
    questions = [{"project_id": assessment["project"]["id"], **q} for assessment in assessments if assessment["status"] == "complete" for q in assessment["result"].get("follow_up_questions", [])]
    return {
        "schema_version": 1,
        "case_id": case["case_id"],
        "created_at": case["created_at"],
        "status": status,
        "candidate": case["candidate"],
        "job": case["job"],
        "project_assessments": assessments,
        "citations": citations,
        "preparation": {
            "required_skills_with_project_evidence": [skill for skill in required if skill.casefold() in demonstrated],
            "required_skills_without_project_evidence": [skill for skill in required if skill.casefold() not in demonstrated],
            "questions": questions,
        },
    }
