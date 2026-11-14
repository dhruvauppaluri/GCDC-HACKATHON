"""Gemini transport for Harsh's Lawyer contract, kept in the integration layer."""
import json

from prototypes.harsh.lawyers import lawyers

from .gemini_client import generate_json


def review_with_gemini(role: str, requirements: list[dict], evidence: list[dict],
                       depth_projects: list[dict], positive_review: dict | None = None) -> dict:
    if role not in lawyers.ROLES:
        raise ValueError("Unknown Lawyer role")
    schema = json.loads(json.dumps(lawyers.REVIEW_SCHEMA))
    artifacts = any(item["source"] in {"depth_repository", "depth_document"} for item in evidence)
    for category in lawyers.CATEGORIES:
        point = schema["properties"][category]["items"]["properties"]
        point["kind"]["enum"] = (["unknown"] if role == "negative" else
                                  ["supported_claim", "artifact_evidence"] if artifacts else ["supported_claim"])
        point["evidence_ids"]["items"]["enum"] = [item["id"] for item in evidence]
    system = f"""You are the {role} Lawyer. {lawyers.ROLES[role]}
Assess projects, work experience, and skills or required knowledge against the job.
Every point is a full sentence explaining role relevance. Cite supplied evidence IDs.
Résumé statements and self-rated skills are candidate claims, not verified skill.
An artifact_evidence point needs a cited Depth repository or document excerpt.
The skeptic should mark missing information as unknown, not a proven gap.
Do not treat missing internships or unrequested tools as weaknesses.
Do not infer poor ability from missing evidence. Do not invent strengths.
Depth ratings show project evidence, not authorship or job fit.
The positive Lawyer's findings are supplied to the skeptic to avoid contradictory arguments."""
    result = generate_json(system, {"requirements": requirements, "evidence": evidence,
                                    "depth_projects": depth_projects, "positive_review": positive_review},
                           schema, model_env="LAWYER_GEMINI_MODEL")
    return lawyers.validate(result, requirements, evidence)
