# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence (confirmed by implementation request)
- Owned directories: `backend/depth/`, `tests/depth/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: depth prototype implementation
- Status: implemented locally; integration pending
- Completed work: foundation, read-only ingestion, evidence-gated evaluator, mock/live modes, answer revisions, API, tests
- Work in progress: final verification and status report
- Next steps: human-review calibration examples, confirm GitHub identities and shared contract, integrate with Judge
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: draft Depth HTTP API in `docs/api-contracts.md`
- Dependencies: approved shared contract, optional OpenAI API credential
- Blockers: integration owner and GitHub identity mappings pending; live API credentials unavailable for verification
- Files modified: `backend/depth/`, `tests/depth/`, own status file; initialization files under `.agents/`, `.github/`, `docs/`, `scripts/`, and root
- Latest relevant commit or PR: none
- Last updated: 2026-11-09T13:06:47Z
