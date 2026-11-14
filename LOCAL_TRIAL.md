# Local integration trial

This branch combines the current Depth, Rishi, and Harsh prototypes for a local trial. It is not a production hiring evaluator. The original candidate résumé PDF and its contact details are not bundled; `backend/web/fixtures/dhruva_trial_profile.json` seeds its job-relevant content and project links. The seeded 1/5 skill ratings are placeholders, not Dhruva's self-assessment.

## What the trial does

1. Sign in to the seeded profile, or complete onboarding yourself. GitHub, website, and résumé projects can be selected in the profile.
2. **Role matches** always shows curated jobs and active, visible 2027 HW/CS/PM internships from [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships). The source cache refreshes at most once every four hours and is checked every five minutes while the web server is running. A quick advocate, skeptic, and tentative label use only profile claims and listing titles. The listing file has no full job descriptions.
3. **Paste a job** accepts a full description, suggests HW/CS/PM, lets you correct the track, and saves the role to your local account. Pasted jobs appear alongside auto matches even if their track is outside your current target paths.
4. **Interested** starts selected-project Depth evaluations. For a Simplify listing, Research first attempts to read the linked original posting and extract a draft description. If that page blocks extraction, the case says so and the provisional Judge returns `needs_job_description`.
5. When Depth finishes or partially fails, the Paralegal bridge extracts cited résumé claims (Rishi's SWE extractor for CS; local term extraction for HW/PM), then both Lawyers receive the same frozen evidence. Rishi's fictional SWE applications appear only as illustrative comparisons; their simulated outcomes never enter a verdict. The local provisional Judge summarizes the Lawyers and keeps eligibility separate. Rishi and Harsh's shared Judge is still pending.

All case and review endpoints require the candidate's session. The browser never sends a session cookie to a separate Lawyer service. The local Ollama model receives the candidate's résumé claims and job information through the local backend.

## Windows setup

In PowerShell, from the repository root on the **trial branch**:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
cd web
npm ci
npm run build
cd ..
.\.venv\Scripts\python.exe -m backend.web.seed_trial
Get-Content .web-data\local-trial-login.txt
ollama pull qwen3:4b
```

Start Ollama if it is not already running. Then open two PowerShell windows at the repository root. In the first:

```powershell
$env:DEPTH_WORKERS = "1"
$env:DEPTH_OLLAMA_MODEL = "qwen3:4b"
# Optional but recommended for multiple GitHub projects: $env:GITHUB_TOKEN = gh auth token
.\.venv\Scripts\python.exe -m uvicorn backend.depth.api:app --host 127.0.0.1 --port 8000
```

In the second:

```powershell
$env:DEPTH_INTEGRATION_MODE = "ollama"
$env:LAWYER_OLLAMA_MODEL = "qwen3:4b"
.\.venv\Scripts\python.exe -m uvicorn backend.web.api:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010` and use the generated local login. The seed does not contain a password; the command generates one on that laptop. If you prefer Codex for Depth, set `DEPTH_INTEGRATION_MODE=codex` on the web process and sign in to the Codex CLI on that laptop. The two Lawyers still require Ollama.

GitHub's unauthenticated API rate limit can interrupt analysis of several repositories because Depth inspects individual files. Set `GITHUB_TOKEN` only in the Depth process environment if you have a GitHub token; do not put it in a file or commit it. A partially inspected repository keeps a limitation rather than silently claiming full verification.

## What has been checked

- Local backend tests and the frontend build pass.
- A real Codex run analyzed the NeuroSig GitHub repository through the pasted-job case. Other repository reads hit GitHub's anonymous rate limit and were marked failed in that case.
- Rishi's extractor, Harsh's case input adapter, and a controlled two-Lawyer review were exercised in tests. No local Ollama server was available on the Mac, so a live Qwen Lawyer/Judge run remains for the Windows laptop.
