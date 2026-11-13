# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Track-specific Depth scoring and selected-project handoff to Paralegal/Lawyer/Judge
- Status: draft PR #3 opened from `agent/dhruva/depth-integration`; Depth now supports `DEPTH_CODEX_HOME` and reports local-state permission failures clearly; Depth tests pass
- Completed work: Depth foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; onboarding website and 13 synthetic user/resume JSON fixtures; Venya's pending role added on main
- Work in progress: peer review of the versioned case contract and Rishi/Harsh integration handoff; Harsh's controlled-response Lawyer handoff succeeded, but his live Codex evaluation awaits a writable authenticated local state directory
- Next steps: obtain Rishi and Harsh's GitHub identities and technical path allocation, human-review HW/CS/PM calibration examples, agree on authenticated case handoff for their Lawyer service, connect their Paralegal/Lawyer/Judge implementation to the case bundle
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: track-specific Depth HTTP API and authenticated website case bundle in `docs/api-contracts.md`; peer handoff in `docs/rishi-harsh-integration-handoff.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: peer identities and path allocation, human-reviewed calibration, Venya's repo invitation; private-repo branch protection requires a plan upgrade or a different enforcement setup
- Files modified: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, own status file, integration-reviewed docs and shared context on feature branch
- Latest relevant commit or PR: draft PR #3, Codex state-directory recovery update
- Last updated: 2026-11-13
