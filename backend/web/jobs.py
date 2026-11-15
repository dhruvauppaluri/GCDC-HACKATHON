"""Parse and screen candidate-supplied jobs and Simplify listings."""
import re

TRACKS = {"HW": "hardware", "CS": "software", "PM": "product"}

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

TRACK_TERMS = {
    "hardware": ("fpga", "asic", "verilog", "pcb", "embedded", "circuit", "semiconductor", "electrical", "hardware"),
    "software": ("software", "developer", "programmer", "frontend", "backend", "full stack", "web", "cloud", "algorithm", "api"),
    "product": ("product manager", "product management", "roadmap", "user research", "stakeholder", "product strategy", "prioritization"),
}


def parse_job_description(description: str, track: str | None = None, title: str = "", company: str = "") -> dict:
    """Extract a reviewable job draft; the original description remains authoritative."""
    description = description.strip()
    if len(description) < 40 or len(description) > 20_000:
        raise ValueError("Paste a job description between 40 and 20,000 characters")
    if track is not None and track not in TRACK_TERMS:
        raise ValueError("Choose hardware, software, or product")
    lines = [line.strip(" \t•-*–") for line in description.splitlines() if line.strip()]
    first_phrase = re.split(r"[.!?]\s+", lines[0], maxsplit=1)[0]
    heading = title.strip() or next((line for line in [first_phrase, *lines[:3]] if len(line) <= 120), "Pasted role")
    text = (heading + " " + description).casefold()
    scores = {name: sum(text.count(term) for term in terms) for name, terms in TRACK_TERMS.items()}
    inferred = max(scores, key=scores.get) if max(scores.values()) else "software"
    chosen = track or inferred
    known = list(dict.fromkeys(skill for skill in SKILL_OPTIONS[{"hardware": "HW", "software": "CS", "product": "PM"}[chosen]]))
    # Longer names win before short aliases such as C and SQL.
    found = [skill for skill in sorted(known, key=len, reverse=True) if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", description, re.I)]
    preferred_text = " ".join(match.group(1) for match in re.finditer(
        r"(?:preferred|nice to have|bonus)\s*:?\s*([^\n]+)", description, re.I,
    ))
    preferred = [skill for skill in found if re.search(r"(?<!\w)" + re.escape(skill) + r"(?!\w)", preferred_text, re.I)]
    required = [skill for skill in found if skill not in preferred]
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


def lightweight_screen(matched: list[str], gaps: list[str], projects: list[str], *, title_only: bool = False,
                       fetched_description: bool = False) -> dict:
    """Fast claim-only advocate/skeptic pass for the discovery list."""
    advocate = [f"Your profile lists {', '.join(matched[:3])}; the listing title mentions these terms, but its full requirements are not available yet." if title_only else f"Your profile lists {', '.join(matched[:3])}."] if matched else []
    if projects:
        advocate.append(f"Your selected project {projects[0]} may be relevant; its depth has not been checked for this job.")
    skeptic = [f"Your profile does not yet show project evidence for {', '.join(gaps[:3])}."] if gaps else []
    return {
        "advocate": advocate, "skeptic": skeptic,
        "verdict": "worth_exploring" if advocate else "more_info_needed",
        "confidence": "low", "stage": "profile_screen",
        "note": ("Listing-title screen only; the linked description is still being fetched or could not be read. " if title_only
                 else "Quick screen from terms in the linked description and candidate-reported skills; qualification status is verified only in the full review. " if fetched_description
                 else "Quick screen from candidate-reported skills and project titles only. ") + "Choose Interested for the full evidence review.",
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
        matched = [s for s in signals if s.casefold() in skill_names]
        # Feed term extraction is deliberately broad. Do not present a term as
        # a missing mandatory qualification before the full JD is parsed.
        gaps = [] if job.get("source") == "simplify" else [s for s in required if s.casefold() not in skill_names]
        project_context = [p["title"] for p in selected_projects if any(s.casefold() in (p.get("title", "") + " " + p.get("summary", "")).casefold() for s in signals)][:2]
        source = job.get("source") or "unspecified"
        result.append({**job, "matched_skills": matched, "skill_gaps": gaps, "project_context": project_context, "source": source,
                       "screening": lightweight_screen(matched, gaps, project_context, title_only=title_only,
                                                       fetched_description=job.get("source") == "simplify" and not title_only)})
    return sorted(result, key=lambda j: (j["source"] != "pasted", -len(j["matched_skills"]), -len(j["project_context"]), len(j["skill_gaps"]), -int(j.get("date_posted") or 0), j["title"]))
