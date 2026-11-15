"""Stress test the requirement -> paralegal -> matcher -> Judge path with synthetic applicants.

Usage (needs GEMINI_API_KEY in the environment for the semantic path):
    set -a; . ./.env; set +a
    .venv/bin/python -m scripts.calibration.run_stress --seeds 3 --repeat 2 --out reports/calibration/stress.json

Checks: monotonicity of score in intended level, keyword-stuffing and negation
resistance, irrelevant-applicant floor, within-level spread (paraphrase
stability) and independent-rerun stability (fresh caches). Levels are
synthetic by construction; this is not human-label calibration.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import statistics
import sys
import tempfile

from backend.web import matching, paralegal
from backend.web.judge import judge_case
from backend.web.requirements import extract_requirements
from prototypes.harsh.lawyers.lawyers import CATEGORIES

from .synth import LEVELS, SKILLS, make_jd, make_resume


def build_inputs(jd: dict, resume: dict, model: str) -> dict:
    groups = extract_requirements(jd["description"], jd["title"], jd["company"], model)
    evidence = []
    extracted = paralegal.extract(resume["text"])
    facts = []
    if extracted:
        facts = extracted["facts"]
        for index, item in enumerate(extracted["evidence"], 1):
            evidence.append({"id": f"paralegal:{index}", "source": "resume_claim", "location": item["field"],
                             "excerpt": item["quote"], "signal": item["signal"], "terms": item["terms"],
                             **{k: item[k] for k in ("skills", "specific", "has_outcome", "ownership") if k in item}})
    for index, text in enumerate(resume["artifacts"], 1):
        evidence.append({"id": f"depth:synthetic:{index}", "source": "depth_repository", "excerpt": text})
    job = {"source": "pasted", "description_status": "full", "requirements_status": "source_checked",
           "eligibility_requirements": [g["text"] for g in groups if g["kind"] == "eligibility"]}
    return {"job": job, "requirements": groups, "evidence": evidence, "full_evidence": evidence, "candidate_facts": facts}


def score_pair(jd: dict, resume: dict, model: str) -> dict:
    empty = {c: [] for c in CATEGORIES}
    inputs = build_inputs(jd, resume, model)
    result = judge_case(inputs, empty, empty)
    return {"track": resume["track"], "jd": jd["title"], "level": resume["level"], "seed": resume["seed"],
            "score": result["match_score"], "low": (result.get("score_range") or {}).get("low"),
            "coverage": {r["text"][:60]: [r["coverage"], r["status"]] for r in result["requirements"]},
            "n_required": sum(r["kind"] == "required" for r in result["requirements"]),
            "n_claims": len([e for e in inputs["evidence"] if e["source"] == "resume_claim"])}


def spearman(xs, ys):
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out, i = [0.0] * len(values), 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else 0.0


def run_pass(args, label: str) -> list[dict]:
    model = os.getenv("REQUIREMENTS_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"))
    jobs = []
    for track in args.tracks:
        for index in range(2):
            jd = make_jd(track, index)
            skills = jd["required"] + jd["preferred"]
            for level in sorted(LEVELS):
                for seed in range(args.seeds):
                    jobs.append((jd, make_resume(track, level, seed, skills)))
    def work(job):
        for attempt in range(3):
            try:
                return score_pair(job[0], job[1], model)
            except Exception as error:  # noqa: BLE001 - report and retry transient model failures
                last = error
        return {"track": job[1]["track"], "jd": job[0]["title"], "level": job[1]["level"], "seed": job[1]["seed"],
                "score": None, "error": f"{type(last).__name__}: {last}"}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(work, jobs))
    print(f"[{label}] scored {sum(r['score'] is not None for r in rows)}/{len(rows)}", file=sys.stderr)
    return rows


def summarize(rows: list[dict]) -> dict:
    good = [r for r in rows if r["score"] is not None]
    by_level = {}
    for level in sorted(LEVELS, reverse=True):
        scores = [r["score"] for r in good if r["level"] == level]
        if scores:
            by_level[LEVELS[level]] = {"n": len(scores), "mean": round(statistics.mean(scores), 1),
                                       "sd": round(statistics.pstdev(scores), 1), "min": min(scores), "max": max(scores)}
    per_track = {}
    for track in sorted({r["track"] for r in good}):
        sub = [r for r in good if r["track"] == track]
        # Pair each applicant seed with the same seed one level up to count monotonicity violations.
        violations = total = 0
        for jd in {r["jd"] for r in sub}:
            for seed in {r["seed"] for r in sub}:
                ladder = {r["level"]: r["score"] for r in sub if r["jd"] == jd and r["seed"] == seed}
                for lo, hi in ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (6, 7)):
                    if lo in ladder and hi in ladder:
                        total += 1
                        violations += ladder[hi] < ladder[lo]
        per_track[track] = {"spearman_level_vs_score": round(spearman([r["level"] for r in sub], [r["score"] for r in sub]), 3),
                            "adjacent_level_inversions": f"{violations}/{total}"}
    mean = lambda name: by_level.get(name, {}).get("mean")
    checks = {
        "stuffed_below_average": mean("stuffed") is not None and mean("stuffed") < mean("average"),
        "learning_only_below_15": mean("learning_only") is not None and mean("learning_only") <= 15,
        "irrelevant_below_10": mean("irrelevant") is not None and mean("irrelevant") <= 10,
        "cracked_at_least_85": mean("cracked") is not None and mean("cracked") >= 85,
        "strong_above_solid_above_average": all(mean(x) is not None for x in ("strong", "solid", "average")) and mean("strong") > mean("solid") > mean("average"),
        "max_within_level_sd_le_8": all(v["sd"] <= 8 for k, v in by_level.items() if k not in {"solid", "average", "weak"}),
    }
    return {"by_level": by_level, "per_track": per_track, "checks": checks,
            "failed_scores": [{k: r[k] for k in ("track", "jd", "level", "seed", "error")} for r in rows if r["score"] is None]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--repeat", type=int, default=2, help="independent passes with fresh caches (stability)")
    parser.add_argument("--tracks", nargs="+", default=["HW", "CS", "PM"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", default="reports/calibration/stress.json")
    args = parser.parse_args()
    passes = []
    for n in range(args.repeat):
        os.environ["MATCH_CACHE_PATH"] = str(Path(tempfile.mkdtemp()) / "cache.sqlite3")
        extract_requirements.cache_clear()
        passes.append(run_pass(args, f"pass {n + 1}"))
    report = {"matcher": matching.MATCHER_VERSION, "paralegal": paralegal.PARALEGAL_VERSION, "seeds": args.seeds,
              "verifier": "gemini" if matching.semantic_available() else "deterministic_ontology",
              "note": "Levels are synthetic by construction, not human labels.", "pass1": summarize(passes[0])}
    if len(passes) > 1:
        diffs = [abs(a["score"] - b["score"]) for a, b in zip(passes[0], passes[1]) if a["score"] is not None and b["score"] is not None]
        report["rerun_stability"] = {"pairs": len(diffs), "mean_abs_diff": round(statistics.mean(diffs), 2) if diffs else None,
                                     "max_abs_diff": max(diffs) if diffs else None,
                                     "share_within_5_points": round(sum(d <= 5 for d in diffs) / len(diffs), 3) if diffs else None}
        report["largest_rerun_differences"] = sorted(
            ({"track": a["track"], "jd": a["jd"], "level": a["level"], "seed": a["seed"], "pass1": a["score"], "pass2": b["score"],
              "n_required": [a["n_required"], b["n_required"]], "n_claims": [a["n_claims"], b["n_claims"]]}
             for a, b in zip(passes[0], passes[1]) if a["score"] is not None and b["score"] is not None and abs(a["score"] - b["score"]) > 5),
            key=lambda r: -abs(r["pass1"] - r["pass2"]))[:20]
    report["rows"] = passes[0]
    report["rows_pass2"] = passes[1] if len(passes) > 1 else None
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
