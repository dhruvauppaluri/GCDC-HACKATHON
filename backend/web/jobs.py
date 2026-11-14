"""Curated jobs and a small adapter for the draft Research output."""
import json
from pathlib import Path
import re

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
    "CS": ["Python", "Java", "TypeScript", "React", "CSS", "APIs", "SQL", "C++", "Linux", "algorithms", "testing", "distributed systems"],
    "PM": ["user research", "prioritization", "analytics", "SQL", "roadmapping", "product strategy", "technical communication", "APIs", "stakeholder management", "metrics", "experimentation"],
}

TRACK_TERMS = {
    "hardware": ("fpga", "asic", "verilog", "pcb", "embedded", "circuit", "semiconductor", "electrical", "hardware"),
    "software": ("software", "developer", "programmer", "frontend", "backend", "full stack", "web", "cloud", "algorithm", "api"),
    "product": ("product manager", "product management", "roadmap", "user research", "stakeholder", "product strategy", "prioritization"),
}


def skill_alternatives(requirement: str) -> list[str]:
    """A requirement such as 'Python or Java' needs one of its options."""
    return [part.strip() for part in re.split(r"\s+or\s+", requirement, flags=re.I) if part.strip()]


def parse_job_description(description: str, track: str | None = None, title: str = "", company: str = "") -> dict:
    """Extract a reviewable job draft; the original description remains authoritative."""
    description = description.strip()
    if len(description) < 40 or len(description) > 20_000:
        raise ValueError("Paste a job description between 40 and 20,000 characters")
    if track is not None and track not in TRACK_TERMS:
        raise ValueError("Choose hardware, software, or product")
    sectioned = re.sub(r"(?<=[.!?])\s+(?=(?:preferred|minimum|required|basic|nice[- ]to[- ]have|bonus)\b[^:\n]{0,30}:)",
                       "\n", description, flags=re.I)
    lines = [line.strip(" \t•-*–") for line in sectioned.splitlines() if line.strip()]
    first_phrase = re.split(r"[.!?]\s+", lines[0], maxsplit=1)[0]
    heading = title.strip() or next((line for line in [first_phrase, *lines[:3]] if len(line) <= 120), "Pasted role")
    text = (heading + " " + description).casefold()
    scores = {name: sum(text.count(term) for term in terms) for name, terms in TRACK_TERMS.items()}
    inferred = max(scores, key=scores.get) if max(scores.values()) else "software"
    chosen = track or inferred
    known = list(dict.fromkeys(skill for skill in SKILL_OPTIONS[{"hardware": "HW", "software": "CS", "product": "PM"}[chosen]]))
    required, preferred = [], []
    section = "context"
    heading_pattern = re.compile(r"^(preferred|minimum|required|basic|nice[- ]to[- ]have|bonus)(?:\s+(?:qualifications|skills|requirements))?\s*:?\s*$", re.I)
    inline_pattern = re.compile(r"^(preferred|minimum|required|basic|nice[- ]to[- ]have|bonus)(?:\s+(?:qualifications|skills|requirements))?\s*:\s*(.+)$", re.I)
    for line in lines:
        if match := heading_pattern.fullmatch(line):
            section = "preferred" if match.group(1).casefold() in {"preferred", "nice to have", "nice-to-have", "bonus"} else "required"
            continue
        if match := inline_pattern.match(line):
            section = "preferred" if match.group(1).casefold() in {"preferred", "nice to have", "nice-to-have", "bonus"} else "required"
            line = match.group(2)
        # Prefer long terms so 'C' cannot also match the beginning of 'C++'.
        spans = []
        for skill in sorted(known, key=len, reverse=True):
            for match in re.finditer(r"(?<!\w)" + re.escape(skill) + r"(?![\w+])", line, re.I):
                if not any(match.start() < end and start < match.end() for start, end, _ in spans):
                    spans.append((match.start(), match.end(), skill))
        spans.sort()
        groups = []
        for start, end, skill in spans:
            if groups and re.fullmatch(r"\s+or\s+", line[groups[-1][-1][1]:start], re.I):
                groups[-1].append((start, end, skill))
            else:
                groups.append([(start, end, skill)])
        if section != "context":
            destination = preferred if section == "preferred" else required
            destination.extend(" or ".join(item[2] for item in group) for group in groups)
    required = list(dict.fromkeys(required))
    preferred = [skill for skill in dict.fromkeys(preferred) if skill not in required]
    return {
        "track": chosen, "inferred_track": inferred, "title": heading[:120],
        "company": company.strip()[:120] or "Pasted job", "description": description,
        "required_skills": required, "preferred_skills": preferred,
        "parsing_note": "Keyword extraction is a draft. Review the track and requirements against the full description.",
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


def lightweight_screen(matched: list[str], gaps: list[str], projects: list[str], *, title_only: bool = False) -> dict:
    """Fast claim-only advocate/skeptic pass for the discovery list."""
    advocate = [f"Your profile lists {', '.join(matched[:3])}; the listing title mentions these terms, but its full requirements are not available yet." if title_only else f"Your profile lists {', '.join(matched[:3])}."] if matched else []
    if projects:
        advocate.append(f"Your selected project {projects[0]} may be relevant; its depth has not been checked for this job.")
    skeptic = [f"Your profile does not yet show project evidence for {', '.join(gaps[:3])}."] if gaps else []
    return {
        "advocate": advocate, "skeptic": skeptic,
        "verdict": "worth_exploring" if advocate else "more_info_needed",
        "confidence": "low", "stage": "profile_screen",
        "note": ("Listing-title screen only; requirements need the original posting. " if title_only else "Quick screen from candidate-reported skills and project titles only. ") + "Choose Interested for the full evidence review.",
    }


def match_jobs(profile: dict, jobs: list[dict]):
    target_tracks = {TRACKS[t] for t in profile["target_tracks"] if t in TRACKS}
    skill_names = {name.casefold() for track in profile["target_tracks"] for name, level in profile["skills"].get(track, {}).items() if level >= 1}
    selected_projects = [p for p in profile.get("projects", []) if p.get("selected")]
    result = []
    for job in jobs:
        if job["track"] not in target_tracks and job.get("source") != "pasted":
            continue
        required = [str(s) for s in job.get("required_skills", [])]
        preferred = [str(s) for s in job.get("preferred_skills", [])]
        title_only = job.get("source") == "simplify" and job.get("description_status") == "listing_only"
        signals = [str(s) for s in job.get("title_signals", [])] if title_only else required + preferred
        matched = [s for s in signals if any(option.casefold() in skill_names for option in skill_alternatives(s))]
        gaps = [s for s in required if not any(option.casefold() in skill_names for option in skill_alternatives(s))]
        project_context = [p["title"] for p in selected_projects if any(option.casefold() in (p.get("title", "") + " " + p.get("summary", "")).casefold() for s in signals for option in skill_alternatives(s))][:2]
        source = job.get("source") or ("curated" if job["job_id"] in {j["job_id"] for j in SEED_JOBS} else "research")
        result.append({**job, "matched_skills": matched, "skill_gaps": gaps, "project_context": project_context, "source": source,
                       "screening": lightweight_screen(matched, gaps, project_context, title_only=title_only)})
    return sorted(result, key=lambda j: (j["source"] != "pasted", -len(j["matched_skills"]), -len(j["project_context"]), len(j["skill_gaps"]), -int(j.get("date_posted") or 0), j["title"]))

