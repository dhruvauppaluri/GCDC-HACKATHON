"""Human gold-set tooling: export cases for labeling, then measure the matcher against reviewers.

    # 1. write blind labeling sheets (no scores shown to reviewers)
    .venv/bin/python -m scripts.calibration.gold export --n 60 --out reports/calibration/gold
    # 2. each reviewer fills `labels` in their own copy: <out>/cases.jsonl -> <out>/labels-<name>.jsonl
    # 3. report agreement, accuracy against consensus, and score-vs-rating correlation
    .venv/bin/python -m scripts.calibration.gold evaluate --dir reports/calibration/gold

Per requirement a reviewer answers supported | partial | not_shown (from the résumé text
alone: does it show this qualification for an internship?), plus an overall 1-5 fit rating.
Nothing here is a label until a human fills it in.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import random
import statistics

from .run_stress import spearman

BUCKETS = ("supported", "partial", "not_shown")


def bucket(coverage: float) -> str:
    return "supported" if coverage >= 0.75 else "partial" if coverage >= 0.25 else "not_shown"


def export(args):
    from backend.web.judge import judge_case
    from backend.web.requirements import extract_requirements
    from prototypes.harsh.lawyers.lawyers import CATEGORIES
    from .run_stress import build_inputs
    from .synth import LEVELS, make_jd, make_resume
    import os
    model = os.getenv("REQUIREMENTS_MODEL", os.getenv("GEMINI_MODEL", "gemini-3.5-flash"))
    rng = random.Random(args.seed)
    cases = []
    tracks = ["HW", "CS", "PM"]
    for i in range(args.n):
        track, index, level = tracks[i % 3], rng.randrange(2), rng.choice([7, 6, 5, 4, 3, 2, 1])
        jd = make_jd(track, index)
        resume = make_resume(track, level, rng.randrange(10_000), jd["required"] + jd["preferred"])
        inputs = build_inputs(jd, resume, model)
        decision = judge_case(inputs, {c: [] for c in CATEGORIES}, {c: [] for c in CATEGORIES})
        cases.append({"pair_id": f"g{i:03d}", "track": track, "job_text": jd["description"], "resume_text": resume["text"],
                      "requirements": [{"id": r["id"], "kind": r["kind"], "text": r["text"]} for r in inputs["requirements"] if r["kind"] != "eligibility"],
                      "_prediction": {r["id"]: r["coverage"] for r in decision["requirements"]}, "_score": decision["match_score"],
                      "_synthetic_level": LEVELS[level]})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    blind = [{k: v for k, v in c.items() if not k.startswith("_")} | {"labels": {"requirements": {}, "overall": None}} for c in cases]
    (out / "cases.jsonl").write_text("\n".join(json.dumps(c) for c in blind) + "\n")
    (out / "_predictions.jsonl").write_text("\n".join(json.dumps({k: c[k] for k in ("pair_id", "_prediction", "_score", "_synthetic_level")}) for c in cases) + "\n")
    print(f"wrote {len(cases)} blind cases to {out}/cases.jsonl (keep _predictions.jsonl away from reviewers)")


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in BUCKETS) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def bootstrap(values: list[float], reps: int = 1000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(reps))
    return round(means[int(0.025 * reps)], 3), round(means[int(0.975 * reps)], 3)


def evaluate(args):
    folder = Path(args.dir)
    predictions = {p["pair_id"]: p for p in map(json.loads, (folder / "_predictions.jsonl").read_text().splitlines())}
    sheets = {path.stem.removeprefix("labels-"): [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
              for path in sorted(folder.glob("labels-*.jsonl"))}
    if not sheets:
        raise SystemExit("No labels-<reviewer>.jsonl files yet; calibration stays pending.")
    labels = {name: {c["pair_id"]: c["labels"] for c in rows if c["labels"].get("requirements")} for name, rows in sheets.items()}
    report = {"reviewers": {k: len(v) for k, v in labels.items()}}
    pairs = [(a, b) for i, a in enumerate(labels) for b in list(labels)[i + 1:]]
    report["pairwise_kappa"] = {}
    for a, b in pairs:
        xs, ys = [], []
        for pid in labels[a].keys() & labels[b].keys():
            for rid in labels[a][pid]["requirements"].keys() & labels[b][pid]["requirements"].keys():
                xs.append(labels[a][pid]["requirements"][rid])
                ys.append(labels[b][pid]["requirements"][rid])
        report["pairwise_kappa"][f"{a}~{b}"] = {"n": len(xs), "kappa": round(kappa(xs, ys), 3)}
    # consensus = majority of reviewers; ties are dropped rather than guessed
    rows, scores, ratings = [], [], []
    for pid, prediction in predictions.items():
        votes = [labels[name][pid] for name in labels if pid in labels[name]]
        if not votes:
            continue
        for rid, coverage in prediction["_prediction"].items():
            counts = Counter(v["requirements"].get(rid) for v in votes if v["requirements"].get(rid))
            top = counts.most_common(2)
            if top and (len(top) == 1 or top[0][1] > top[1][1]):
                rows.append((bucket(coverage), top[0][0]))
        overall = [v["overall"] for v in votes if v.get("overall")]
        if overall and prediction["_score"] is not None:
            scores.append(prediction["_score"]); ratings.append(statistics.mean(overall))
    hits = [p == t for p, t in rows]
    report["requirement_accuracy_vs_consensus"] = {"n": len(rows), "accuracy": round(statistics.mean(hits), 3) if hits else None,
                                                   "ci95": bootstrap([float(h) for h in hits]) if hits else None}
    report["confusion"] = {f"pred={p}|human={t}": c for (p, t), c in sorted(Counter(rows).items())}
    report["false_credit_rate"] = round(sum(p == "supported" and t == "not_shown" for p, t in rows) / max(1, sum(t == "not_shown" for _, t in rows)), 3)
    report["missed_credit_rate"] = round(sum(p == "not_shown" and t == "supported" for p, t in rows) / max(1, sum(t == "supported" for _, t in rows)), 3)
    report["score_vs_overall_rating_spearman"] = round(spearman(scores, ratings), 3) if len(scores) > 2 else None
    print(json.dumps(report, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export"); e.add_argument("--n", type=int, default=60); e.add_argument("--seed", type=int, default=7)
    e.add_argument("--out", default="reports/calibration/gold"); e.set_defaults(fn=export)
    v = sub.add_parser("evaluate"); v.add_argument("--dir", default="reports/calibration/gold"); v.set_defaults(fn=evaluate)
    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
