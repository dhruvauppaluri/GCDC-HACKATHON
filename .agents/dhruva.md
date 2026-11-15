# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Remove assessment-limit copy from the website and probe weak applicant reviews across SWE, PM, and HW.
- Status: Assessment limits are no longer rendered in project cards. Six live synthetic weak/partial cases and three strong artifact controls were run across the three tracks with both Gemini Lawyers and the Gemini Judge. Weak cases scored 0; partial claim-only cases scored 11–22; strong artifact controls scored 100. The probe exposed partial credit for negated skills, which was fixed in the integration Judge. Paralegal claim signals now discard negated mentions and recognize user interviews as user research. The integration filters unsupported claim-only Advocate points, and the Judge hides strengths for uncovered requirements. The full test suite (80 tests), frontend build, and local browser check passed. No key was written to the repository.
- Completed work: Depth foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; onboarding website and 13 synthetic user/resume JSON fixtures; Venya's pending role added on main
- Work in progress: Windows-ready Ollama and opt-in Gemini provider; background JD coverage depends on employer pages being accessible while the web process runs
- Next steps: calibrate requirement extraction and score bands against human-reviewed HW/CS/PM cases; hand the integration Judge to Rishi and Harsh for review
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: track-specific Depth HTTP API and authenticated website case bundle in `docs/api-contracts.md`; peer handoff in `docs/rishi-harsh-integration-handoff.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: peer identities and path allocation, human-reviewed calibration, Venya's repo invitation; private-repo branch protection requires a plan upgrade or a different enforcement setup
- Files modified: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, own status file, integration-reviewed docs and shared context on feature branch
- Latest relevant commit or PR: draft PR #4 from `agent/dhruva/local-integration-test`; draft PR #3 remains unchanged
- Last updated: 2026-11-15
