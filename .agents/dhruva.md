# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Fix GitHub profile import rate limiting in the website.
- Status: Profile import now reads bounded public GitHub repository cards from the profile page instead of spending unauthenticated REST quota. Live import found eight public repositories on Dhruva's profile; full suite: 102 tests passed. No Gemini evaluation was started during this fix.
- Completed work: Depth foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; onboarding website and 13 synthetic user/resume JSON fixtures; Venya's pending role added on main
- Work in progress: Windows-ready Ollama and opt-in Gemini provider; background JD coverage depends on employer pages being accessible while the web process runs
- Next steps: calibrate requirement extraction and score bands against human-reviewed HW/CS/PM cases; hand the integration Judge to Rishi and Harsh for review; review the Hanzel branch with the team
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: track-specific Depth HTTP API and authenticated website case bundle in `docs/api-contracts.md`; peer handoff in `docs/rishi-harsh-integration-handoff.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: peer identities and path allocation, human-reviewed calibration, Venya's repo invitation; private-repo branch protection requires a plan upgrade or a different enforcement setup
- Files modified: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, own status file, integration-reviewed docs and shared context on feature branch
- Latest relevant commit or PR: PR #6 merged into `main`; profile import fix in `agent/dhruva/github-profile-import`.
- Last updated: 2026-11-15
