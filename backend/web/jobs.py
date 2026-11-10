"""Curated jobs and a small adapter for the draft Research output."""
import json
from pathlib import Path

TRACKS = {"HW": "hardware", "CS": "software", "PM": "product"}

SEED_JOBS = [
    {"job_id": "hw-1", "track": "hardware", "title": "FPGA Design Intern", "company": "Northstar Labs", "required_skills": ["SystemVerilog", "FPGA", "digital design"], "preferred_skills": ["simulation", "Python"]},
    {"job_id": "hw-2", "track": "hardware", "title": "Embedded Systems Engineer", "company": "Fieldnote Robotics", "required_skills": ["C", "embedded systems", "electronics"], "preferred_skills": ["PCB design", "Python"]},
    {"job_id": "hw-3", "track": "hardware", "title": "PCB Design Associate", "company": "Orbit Devices", "required_skills": ["PCB design", "electronics", "schematics"], "preferred_skills": ["Altium", "testing"]},
    {"job_id": "cs-1", "track": "software", "title": "Software Engineering Intern", "company": "Threadline", "required_skills": ["Python", "APIs", "SQL"], "preferred_skills": ["React", "testing"]},
    {"job_id": "cs-2", "track": "software", "title": "Frontend Engineer", "company": "Daylight Studio", "required_skills": ["TypeScript", "React", "CSS"], "preferred_skills": ["accessibility", "testing"]},
    {"job_id": "cs-3", "track": "software", "title": "Systems Software Intern", "company": "Copper Cloud", "required_skills": ["C++", "Linux", "algorithms"], "preferred_skills": ["Python", "distributed systems"]},
    {"job_id": "pm-1", "track": "product", "title": "Associate Product Manager", "company": "Tandem", "required_skills": ["user research", "prioritization", "analytics"], "preferred_skills": ["SQL", "roadmapping"]},
    {"job_id": "pm-2", "track": "product", "title": "Technical Product Intern", "company": "Signalworks", "required_skills": ["product strategy", "technical communication", "analytics"], "preferred_skills": ["APIs", "SQL"]},
    {"job_id": "pm-3", "track": "product", "title": "Product Operations Associate", "company": "Mosaic", "required_skills": ["stakeholder management", "metrics", "experimentation"], "preferred_skills": ["user research", "SQL"]},
]

SUGGESTIONS = {
    "HW": ["fpga", "chip", "asic", "embedded", "pcb", "electronics", "circuit", "hardware", "verilog"],
    "CS": ["software", "programming", "coding", "web", "app", "backend", "frontend", "cloud", "algorithm", "computer science"],
    "PM": ["product", "pm", "roadmap", "user research", "customer", "strategy", "market", "prioritization"],
}

SKILL_OPTIONS = {
    "HW": ["SystemVerilog", "FPGA", "digital design", "C", "embedded systems", "electronics", "PCB design", "schematics", "Altium", "simulation", "Python", "testing"],
    "CS": ["Python", "TypeScript", "React", "CSS", "APIs", "SQL", "C++", "Linux", "algorithms", "testing", "distributed systems"],
    "PM": ["user research", "prioritization", "analytics", "SQL", "roadmapping", "product strategy", "technical communication", "APIs", "stakeholder management", "metrics", "experimentation"],
}


def suggest_tracks(interests: str):
    text = interests.casefold()
    scores = {track: sum(1 for term in terms if term in text) for track, terms in SUGGESTIONS.items()}
    return [track for track, score in sorted(scores.items(), key=lambda item: -item[1]) if score]


def load_jobs(path: Path | None):
    jobs = list(SEED_JOBS)
    if path and path.exists():
        raw = json.loads(path.read_text())
        if not isinstance(raw, list):
            raise ValueError("Research jobs file must contain an array")
        for item in raw:
            if not isinstance(item, dict) or not all(item.get(k) for k in ("job_id", "track", "title", "company")):
                continue
            if item["track"] not in TRACKS.values():
                continue
            jobs.append({**item, "required_skills": item.get("required_skills") or [], "preferred_skills": item.get("preferred_skills") or []})
    return list({j["job_id"]: j for j in jobs}.values())


def match_jobs(profile: dict, jobs: list[dict]):
    target_tracks = {TRACKS[t] for t in profile["target_tracks"] if t in TRACKS}
    skill_names = {name.casefold() for track in profile["target_tracks"] for name, level in profile["skills"].get(track, {}).items() if level >= 1}
    selected_projects = [p for p in profile.get("projects", []) if p.get("selected")]
    result = []
    for job in jobs:
        if job["track"] not in target_tracks:
            continue
        required = [str(s) for s in job.get("required_skills", [])]
        preferred = [str(s) for s in job.get("preferred_skills", [])]
        matched = [s for s in required + preferred if s.casefold() in skill_names]
        gaps = [s for s in required if s.casefold() not in skill_names]
        project_context = [p["title"] for p in selected_projects if any(s.casefold() in (p.get("title", "") + " " + p.get("summary", "")).casefold() for s in required + preferred)][:2]
        result.append({**job, "matched_skills": matched, "skill_gaps": gaps, "project_context": project_context, "source": "curated" if job["job_id"] in {j["job_id"] for j in SEED_JOBS} else "research"})
    return sorted(result, key=lambda j: (-len(j["matched_skills"]), -len(j["project_context"]), len(j["skill_gaps"]), j["title"]))
