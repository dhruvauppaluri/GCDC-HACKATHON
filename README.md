# SC-HACK Career Intelligence

An evidence-based project depth prototype for HW, CS, and PM. Read `AGENTS.md` before contributing.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
DEPTH_MODE=mock .venv/bin/uvicorn backend.depth.api:app --reload
```

Open `/docs` for the API. Mock mode runs offline and labels its outputs. For live mode, set `OPENAI_API_KEY` and `DEPTH_MODEL` (an API-supported model), then submit `mode=live`. API access and billing are separate from app subscription access. Data is kept in `.depth-data/`, excluded from Git. One process hosts the local demo worker; this is a prototype, not a production job system.

To evaluate real evidence with your local ChatGPT sign-in and no API key, first run `codex login status` and confirm it says `Logged in using ChatGPT`. Then start the service and submit `mode=codex`. This runs `codex exec` locally with a read-only sandbox and structured output; it uses your Codex plan usage. Set `DEPTH_CODEX_MODEL` only if you want to override the CLI's default model. Do not expose this local service to the public internet.

For a three-track mock demo, copy a synthetic `text` value from `backend/depth/fixtures.py` into the `project_text` form field, then submit its matching `answer` to question `Q1`. These examples are intentionally synthetic and have not been human reviewed. Arbitrary pasted claims remain unassessed in mock mode.

Run `.venv/bin/pytest` for tests. The GitHub remote exists; branch protection has not been verified.

## Candidate website demo

The local candidate experience provides email/password accounts, resumable onboarding, profiles, and preliminary job matches. It stores accounts and extracted resume text in `.web-data/` (ignored by Git). Keep the service on your laptop for the demo.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
cd web && npm install && npm run build && cd ..
.venv/bin/python scripts/seed_web_demo.py
.venv/bin/uvicorn backend.web.api:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010`. The seed command loads 13 synthetic accounts from `tests/web/fixtures/users/*.json` and leaves existing accounts untouched. All sample accounts use `DemoPass123!`. Start with `demo@orbit.local` for a completed mixed HW/CS profile, `taylor.pm@orbit.local` for PM, `jamie.resume@orbit.local` to resume at upload, or `devon.skills@orbit.local` to resume at skills. Each JSON includes its scenario and resume text where applicable; no real candidate data is included. New visitors can sign up with their own email. To develop the frontend, run `cd web && npm run dev` in a second terminal and open `http://127.0.0.1:5173`; Vite proxies `/api` to port 8010.

For Research integration, set `RESEARCH_JOBS_FILE` to a JSON array matching the job shape in `docs/api-contracts.md` before starting the API. Curated roles stay available when no file is configured. Run `.venv/bin/pytest tests/web` and `cd web && npm run build` to verify the website.

## Selected-project Depth handoff

Start the Depth service on port 8000 and the website on port 8010 in separate terminals. Set `DEPTH_INTEGRATION_MODE=codex` on the website process for real local evaluation, or `live` with an API credential; the default `mock` mode deliberately leaves arbitrary projects unassessed. `DEPTH_API_URL` defaults to `http://127.0.0.1:8000`. Sign in, import public GitHub or website projects, select up to five, open a role match, and choose **Assess selected projects**. The resulting case shows project findings and preparation topics. Its authenticated `GET /api/cases/{id}` response is the versioned, cited handoff for the jointly owned Paralegal, Lawyer, and Judge work. Those stages are not implemented by this branch, so this page does not show a hiring verdict.
