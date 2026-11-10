# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence (confirmed by implementation request)
- Owned directories: `backend/depth/`, `tests/depth/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Codex-backed Depth evaluator
- Status: implemented and verified locally; integration pending
- Completed work: foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; Venya's pending role added on main
- Work in progress: calibration and integration
- Next steps: obtain Venya's GitHub username and workstream from her, human-review calibration examples, confirm shared contract, integrate with Judge
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: draft Depth HTTP API in `docs/api-contracts.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: integration owner and GitHub identity mappings pending; Venya's repo invitation needs her username
- Files modified: `backend/depth/`, `tests/depth/`, own status file; draft API contract and README for local Codex mode
- Latest relevant commit or PR: `43d6943` (Venya team context on main)
- Last updated: 2026-11-10T04:32:47Z
