"""Extract cited SWE application evidence from the fictional applicant pool."""

import argparse
from collections import Counter
import json
from pathlib import Path
import re


SIGNALS = {
    "Programming languages": r"Python|Java|JavaScript|TypeScript|C\+\+|Rust|Go",
    "Algorithms and data structures": r"algorithms?|data structures|hash(?:ing| map)|trie|priority queue|graph traversal|(?:breadth|depth)-first search|inverted index|control-flow graphs|topologically sorts|Dijkstra",
    "APIs and application development": r"REST API|API\w*|Spring Boot|FastAPI|Node\.js|React|checkout|dashboard",
    "Databases and persistence": r"SQL|PostgreSQL|Redis|write-ahead log|checkpointing|transactions",
    "Testing and debugging": r"pytest|unit tests?|integration tests?|regression tests?|sanitizers|contract tests?|tested|tests?",
    "Systems and performance": r"concurren\w*|benchmarks?\w*|latency|throughput|failover|cach(?:e|ing)|network partitions|lock contention",
    "Deployment and monitoring": r"Docker|deploy\w*|error monitoring|monitored",
    "Machine learning and evaluation": r"scikit-learn|classifi\w*|forecast\w*|model-serving|precision and recall|held-out|backtested",
}


def extract(record):
    application = record["application"]
    evidence = []
    for field in ("coursework", "projects", "prior_experience"):
        excerpts = application[field]
        if isinstance(excerpts, str):
            excerpts = [excerpts]
        for excerpt in excerpts:
            for signal, pattern in SIGNALS.items():
                matches = re.findall(rf"(?<!\w)(?:{pattern})(?!\w)", excerpt, re.I)
                if matches:
                    evidence.append({
                        "signal": signal,
                        "terms": list(dict.fromkeys(matches)),
                        "field": field,
                        "quote": excerpt,
                    })
    education = application["education"]
    gpa = re.search(r"GPA:\s*(\d+(?:\.\d+)?)/(\d+(?:\.\d+)?)", education)
    return {
        "id": record["id"],
        "company": record["company"],
        "role": record["role"],
        "education": education,
        "gpa": {"value": float(gpa[1]), "scale": float(gpa[2])} if gpa else None,
        "coursework": application["coursework"],
        "projects": application["projects"],
        "prior_experience": application["prior_experience"],
        "evidence": evidence,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, default=Path(__file__).with_name("swe-applications.json"))
    parser.add_argument("--company", choices=["Google", "Walmart"])
    parser.add_argument("--applicant", help="Example: google-01")
    args = parser.parse_args()
    pool = json.loads(args.pool.read_text())
    reports = [
        extract(record) for record in pool["applications"]
        if (args.company is None or record["company"] == args.company)
        and (args.applicant is None or record["id"] == args.applicant)
    ]
    if not reports:
        parser.error("No applications match your selection.")
    counts = Counter()
    for report in reports:
        counts.update({item["signal"] for item in report["evidence"]})
    print(json.dumps({
        "synthetic": pool["synthetic"],
        "applications_reviewed": len(reports),
        "applications_mentioning_each_signal": dict(sorted(counts.items())),
        "applications": reports,
    }, indent=2))


if __name__ == "__main__":
    main()
