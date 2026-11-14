# Lawyer Prototype

Independent local Ollama reviews produce cited pluses and minuses for projects, work experience, and skills/required knowledge. Output is labeled prototype. This is an experimental evidence review, requiring human evaluation before use for decisions.

From this directory:

```sh
ollama pull qwen3:4b
python lawyers.py --paralegal demo-paralegal.json --applicant google-01 --job demo-job.json --model qwen3:4b
```

The bundled application is synthetic, generated from Rishi's google-01 fixture using his Paralegal. The job is an illustrative demo. Full samples are on branch agent/rishi/swe-intern-data under data/fixtures/rishi.

## Review a full candidate case

The Depth integration in PR #3 exposes `GET /api/cases/{case_id}` after a candidate selects projects. Save its authenticated JSON response as `case.json`, then run from this directory:

```sh
python lawyers.py --case case.json --model qwen3:4b > review.json
```

For an offline example using the same case format:

```sh
python lawyers.py --case demo-case-bundle.json --model qwen3:4b > review.json
```

Each Lawyer receives the candidate's profile and resume, job description and required/preferred skills, selected project claims, and completed live/codex Depth findings with source excerpts. Unfinished or mock Depth results are identified as unverified. `review.json` contains both Lawyers' arguments and a `categories` chart of pluses and minuses for projects, work experience, and skills/required knowledge. This prototype does not produce a hiring decision. PR #3 must be merged before the case endpoint is available on main.

Use --preview to inspect inputs. Add --depth path/to/result.json for a completed live/codex Depth result, repeating per selected project. The caller must associate each result with the correct applicant. Mock Depth evidence is excluded. Both Lawyers receive cited Depth summaries, dimension ratings, demonstrated skills, limitations, revision, and the source excerpts. The overall Depth score is project context. It does not become a job-fit score. JSON output contains categories with pluses/minuses and the source evidence. It does not compute a final score or Judge verdict.

Python standard library only. Citation IDs and artifact labels are validated. Semantic accuracy and fairness need calibration across the sample pool. Eligibility requirements are carried through for later evaluation.

## Connect to the Depth service

Start the Depth API from the repository root with `python -m uvicorn backend.depth.api:app --host 127.0.0.1 --port 8000` after installing the repo dependencies. Open `http://127.0.0.1:8000/docs`, submit a selected project using `POST /depth/evaluations` in live or codex mode, and check `GET /depth/evaluations/{evaluation_id}` until it reports complete. Use only evaluations for the selected applicant.

From the prototype directory, run:

```sh
python lawyers.py --paralegal demo-paralegal.json --applicant google-01 --job demo-job.json --model qwen3:4b --depth-id YOUR_EVALUATION_UUID
```

Replace the placeholder with the completed evaluation UUID. Repeat `--depth-id` for additional projects. Use `--depth-port` if the local service uses a different port. You can also use `--depth` with a saved completed response or result.

