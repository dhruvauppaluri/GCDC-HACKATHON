# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Fix GitHub API rate limit failures in Depth without consuming demo Gemini quota.
- Status: Public GitHub ingestion now uses a pinned archive and a blobless Git clone for large repositories, avoiding anonymous REST request exhaustion. Added manual retry for failed Depth checks and reset stale fit reviews before recomputing them. All three Dhruva repositories yielded source evidence without a GitHub token. Full suite: 86 tests passed; frontend build passed. No Gemini evaluation was started during this fix.
- Completed work: Depth foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; onboarding website and 13 synthetic user/resume JSON fixtures; Venya's pending role added on main
- Work in progress: Windows-ready Ollama and opt-in Gemini provider; background JD coverage depends on employer pages being accessible while the web process runs
- Next steps: calibrate requirement extraction and score bands against human-reviewed HW/CS/PM cases; hand the integration Judge to Rishi and Harsh for review; review the Hanzel branch with the team
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: track-specific Depth HTTP API and authenticated website case bundle in `docs/api-contracts.md`; peer handoff in `docs/rishi-harsh-integration-handoff.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: peer identities and path allocation, human-reviewed calibration, Venya's repo invitation; private-repo branch protection requires a plan upgrade or a different enforcement setup
- Files modified: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, own status file, integration-reviewed docs and shared context on feature branch
- Latest relevant commit or PR: draft PR #6 from `agent/dhruva/hanzel-ui` (initial implementation `f78fa08`)
- Last updated: 2026-11-15
