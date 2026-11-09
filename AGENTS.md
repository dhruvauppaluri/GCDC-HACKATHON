# SC-HACK agent collaboration

Before editing, identify the human developer from an explicit declaration, read that person's `.agents/<name>.md`, `.agents/shared-context.md`, `.agents/decisions.md`, and relevant peer files. Inspect the branch and working tree, confirm owned paths and integration dependencies, then modify only authorized files. Update your own status file after meaningful progress.

Dhruva's confirmed workstream is Project Depth Intelligence. Harsh's and Rishi's workstreams and the integration maintainer are unconfirmed. Until an assignment is confirmed, do not modify ownership-sensitive application code for that workstream. Ordinary agents may edit only their owned component and personal status file. Shared contracts, root configuration, workflows, and ownership rules require integration review. Never impersonate another developer, overwrite peer work, push feature work to main, force-push a peer branch, or guess at a peer conflict.

Use `agent/<developer>/<component>` branches and pull requests once a remote exists. Run `python scripts/check_agent_ownership.py --help` for local validation. GitHub settings listed in `docs/github-protection-setup.md` must be configured before claiming enforcement is active.
