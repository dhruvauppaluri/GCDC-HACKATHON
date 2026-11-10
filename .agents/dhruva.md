# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence (confirmed by implementation request)
- Owned directories: `backend/depth/`, `tests/depth/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: add Venya to team context; Codex-backed evaluation adapter remains in progress
- Status: implemented locally; integration pending
- Completed work: foundation, read-only ingestion, evidence-gated evaluator, mock/live modes, answer revisions, API, tests
- Work in progress: Venya identity setup and Codex-backed evaluation adapter
- Next steps: obtain Venya's GitHub username and workstream from her, human-review calibration examples, confirm shared contract, integrate with Judge
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: draft Depth HTTP API in `docs/api-contracts.md`
- Dependencies: approved shared contract, optional OpenAI API credential
- Blockers: integration owner and GitHub identity mappings pending; Venya's repo invitation needs her username
- Files modified: `backend/depth/`, `tests/depth/`, own status file; initialization files under `.agents/`, `.github/`, `docs/`, `scripts/`, and root
- Latest relevant commit or PR: `0b2c011` (initial Depth prototype)
- Last updated: 2026-11-10T04:27:28Z
