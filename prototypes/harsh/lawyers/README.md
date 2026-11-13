# Lawyer Prototype

Independent local Ollama reviews produce cited pluses and minuses for projects, work experience, and skills/required knowledge. Output is labeled prototype. This is an experimental evidence review, requiring human evaluation before use for decisions.

From this directory:

```sh
ollama pull qwen3:4b
python lawyers.py --paralegal demo-paralegal.json --applicant google-01 --job demo-job.json --model qwen3:4b
```

The bundled application is synthetic, generated from Rishi's google-01 fixture using his Paralegal. The job is an illustrative demo. Full samples are on branch agent/rishi/swe-intern-data under data/fixtures/rishi.

Use --preview to inspect inputs. Add --depth path/to/result.json for a completed live/codex Depth result, repeating per selected project. The caller must associate each result with the correct applicant. Mock Depth evidence is excluded. Only evidence excerpts and provenance currently feed the Lawyers; aggregate Depth scores are not consumed. JSON output contains categories with pluses/minuses and the source evidence. It does not compute a final score or Judge verdict.

Python standard library only. Citation IDs and artifact labels are validated. Semantic accuracy and fairness need calibration across the sample pool. Eligibility requirements are carried through for later evaluation.
