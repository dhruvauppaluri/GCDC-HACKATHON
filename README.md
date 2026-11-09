# SC-HACK Depth Intelligence

An evidence-based project depth prototype for four career tracks. Read `AGENTS.md` before contributing.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
DEPTH_MODE=mock .venv/bin/uvicorn backend.depth.api:app --reload
```

Open `/docs` for the API. Mock mode runs offline and labels its outputs. For live mode, set `OPENAI_API_KEY` and `DEPTH_MODEL` (an API-supported model), then submit `mode=live`. API access and billing are separate from app subscription access. Data is kept in `.depth-data/`, excluded from Git. One process hosts the local demo worker; this is a prototype, not a production job system.

For a four-track mock demo, copy a synthetic `text` value from `backend/depth/fixtures.py` into the `project_text` form field, then submit its matching `answer` to question `Q1`. These examples are intentionally synthetic and have not been human reviewed. Arbitrary pasted claims remain unassessed in mock mode.

Run `.venv/bin/pytest` for tests. No GitHub remote or branch protections are configured yet.
