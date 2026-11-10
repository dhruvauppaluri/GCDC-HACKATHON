# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Interactive onboarding and candidate profile
- Status: onboarding implementation and local verification complete on `agent/dhruva/onboarding`; integration review pending
- Completed work: foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; Venya's pending role added on main
- Work in progress: peer review of candidate contract, calibration and integration
- Next steps: obtain Venya's GitHub username and workstream from her, human-review calibration examples, confirm shared contract, integrate with Judge
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: draft Depth HTTP API in `docs/api-contracts.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: base-branch ownership policy needs a reviewed bootstrap update; peer identities and Venya's repo invitation remain pending
- Files modified: `backend/web/`, `tests/web/`, `web/`, own status file; reviewed shared ownership, contracts, README, and local demo script on feature branch
- Latest relevant commit or PR: `43d6943` (Venya team context on main)
- Last updated: 2026-11-10T09:25:00Z
