# Agent identity: Rishi

- Responsible developer: Rishi
- Assigned component: unconfirmed
- Owned directories: this file only
- Prohibited directories: all application and shared paths until assignment
- Current task: pending
- Status: unconfirmed
- Completed work: none recorded
- Work in progress: none recorded
- Next steps: confirm workstream
- Expected inputs: pending
- Expected outputs: pending
- Interfaces exposed: pending
- Dependencies: ownership decision
- Blockers: assignment pending
- Files modified: none recorded
- Latest relevant commit or PR: none
- Last updated: 2026-11-09T00:00:00Z (initial placeholder)

## SWE internship demo dataset

- Task: Prepare Google and Walmart SWE internship examples for the paralegal demo.
- Status: Dataset committed on `agent/rishi/swe-intern-data` with Dhruva's clearance for this addition.
- Files modified: `data/fixtures/rishi/swe-applications.json`, `data/fixtures/rishi/swe_paralegal.py`, and this status file.
- Output: 60 fictional applications, 30 per company, with simulated outcomes in `demo_labels`.
- Integration: The dataset is available as a standalone JSON fixture. Dhruva owns any shared integration changes.
- Dataset commit: `22338c6d83b89149237775c3fdd0eea33cf41167`.
- Extractor commit: `caf6af93d6371979571d2c7beb5cc5eb1e3d8929`. Run `python3 data/fixtures/rishi/swe_paralegal.py --applicant google-01` from the repo root.
- Last updated: 2026-11-13T05:21:51.533Z

## Lawyer citation verification experiment

- Standalone prototype: `data/fixtures/rishi/lawyers_grounded.py` in commit `1377330fb7990033687765dcf4be7fe9e885aee8`.
- Verified locally: preview and nine controlled cases with simulated verifier responses. Live Ollama accuracy and latency remain unmeasured.
- Integration dependency: Harsh and Dhruva review the verifier before adopting it in the shared pipeline.
- Last updated: 2026-11-13T06:59:49.689Z
