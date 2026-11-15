# Hanzel local integration

Hanzel is the candidate-facing UI for the existing GCDC pipeline. It uses authenticated accounts and profiles, not the static values in the Figma prototype.

## Run locally

From the repository root, install the Python and web dependencies as described in the root README, then build the web app:

```sh
cd web && npm install && npm run build && cd ..
```

Start Depth and the web API in separate terminals. For a live Gemini run, put your own keys in an ignored `.env` file (never commit it):

```sh
GEMINI_API_KEY=your-first-project-key
GEMINI_API_KEY_2=your-second-project-key
LAWYER_PROVIDER=gemini
JUDGE_PROVIDER=gemini
DEPTH_INTEGRATION_MODE=gemini
```

Load that file into each terminal before starting the processes. The Depth API uses port 8000 by default, and the web API points to it with `DEPTH_API_URL`. Then open the web API at `http://127.0.0.1:8010`.

```sh
set -a; . ./.env; set +a
.venv/bin/uvicorn backend.depth.api:app --host 127.0.0.1 --port 8000
```

```sh
set -a; . ./.env; set +a
DEPTH_API_URL=http://127.0.0.1:8000 .venv/bin/uvicorn backend.web.api:app --host 127.0.0.1 --port 8010
```

The app stores accounts, résumé text, reports, and bookmarks in `.web-data/`; Depth stores project assessments in `.depth-data/`. Both are ignored by Git. Two Gemini keys are rotated between requests and can fail over across distinct projects, but each project still has its own quota.

## Connected flow

1. Complete onboarding with a PDF, DOCX, or TXT résumé, target paths (HW, CS, PM), skills, and project links. Import GitHub or website projects from Profile. GitHub repositories in the profile enter full reviews; select other projects explicitly.
2. The home page accepts a complete pasted job description, detects a track, and lets the candidate correct the title, company, and track before a full review.
3. Find jobs reads only the SimplifyJobs Summer2027 feed, which the server refreshes on a four-hour cache schedule. Job cards show a preliminary profile screen and the extracted linked description when available. Candidates can paste a missing or corrected description on that card.
4. Selecting **Interested · full review** creates a case. Depth inspects each eligible profile project. The Paralegal extracts résumé signals, the two Lawyers independently argue from the same evidence, and the Judge agent weighs their cases. The displayed match score comes from deterministic documented requirement coverage; the model's narrative cannot alter it.
5. Saved checks lists recent case reports and bookmarked roles per account. Scores are shown only when a Judge score actually exists.

The full review can take time and incurs model requests. If a linked JD is unavailable, the case uses title evidence only until the candidate supplies the full description on the role card. The UI does not invent a score for a quick screen.
