# Agent identity: Harsh

- Responsible developer: Harsh
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

## Lawyer prototype

- Scope: `prototypes/harsh/lawyers/` on `agent/harsh/lawyers-prototype`.
- Status: pushed and smoke tested with local Qwen3 4B on one synthetic application.
- Output: cited pluses and minuses for projects, work experience, and skills/required knowledge.
- Pending: calibrate evidence interpretation, validate with Depth results, and integrate with the Judge.
- Implementation commit: `9e8e11030d6a173777bb8b2ece8f097d75ef6f3b`.

## Integration review fixes

- Scope: separate `agent/harsh/integration-fixes` branch based on Dhruva's draft PR #4, for Dhruva and Rishi to review before integration.
- Fixed: required-skill evidence gate in the provisional Judge, section-aware job parsing with `or` alternatives, Rishi's citation verifier in the website review path plus a literal required-skill citation guard, and review waiting while any selected Depth assessment runs.
- Verification: 41 backend tests and frontend build passed; local Ollama Depth and Lawyer smoke completed; a live SQL-versus-route-project case returned `needs_more_evidence` with SQL unknown.
- Pending: review of these shared integration changes, real résumé/browser rehearsal, and calibration of the provisional Judge and evidence verifier.

