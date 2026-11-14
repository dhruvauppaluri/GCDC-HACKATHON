# Agent identity: Dhruva

- Responsible developer: Dhruva
- Assigned component: Project Depth Intelligence, website, and integration maintainer (confirmed by Dhruva)
- Owned directories: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, this file
- Prohibited directories: other components and restricted shared paths without integration review
- Current task: Local integration trial for pasted jobs, Simplify internship discovery, Depth, Paralegal, Lawyers, and a provisional Judge summary
- Status: separate integration test branch pushed and draft PR #4 opened; pasted-JD and Simplify feed paths are implemented with a sanitized résumé seed for Windows
- Completed work: Depth foundation, evidence ingestion, mock/API/Codex modes, answer revisions, API, tests; onboarding website and 13 synthetic user/resume JSON fixtures; Venya's pending role added on main
- Work in progress: Windows-ready Ollama mode and integration tests; live Qwen Lawyers await the user's Windows laptop, while one real Codex NeuroSig Depth evaluation completed locally
- Next steps: run a live Ollama Depth and Lawyer review on Windows, validate original job-posting extraction, obtain Rishi and Harsh's GitHub identities and path allocation before a merge PR, and replace the provisional local Judge with their reviewed implementation
- Expected inputs: one project, career track, public GitHub URL and/or written evidence, optional candidate answers
- Expected outputs: cited project-depth assessment, questions, versioned revisions
- Interfaces exposed: track-specific Depth HTTP API and authenticated website case bundle in `docs/api-contracts.md`; peer handoff in `docs/rishi-harsh-integration-handoff.md`
- Dependencies: approved shared contract; local Codex CLI sign-in for `mode=codex` or an API credential for `mode=live`
- Blockers: peer identities and path allocation, human-reviewed calibration, Venya's repo invitation; private-repo branch protection requires a plan upgrade or a different enforcement setup
- Files modified: `backend/depth/`, `tests/depth/`, `backend/web/`, `tests/web/`, `web/`, own status file, integration-reviewed docs and shared context on feature branch
- Latest relevant commit or PR: draft PR #4 from `agent/dhruva/local-integration-test`; draft PR #3 remains unchanged
- Last updated: 2026-11-13
