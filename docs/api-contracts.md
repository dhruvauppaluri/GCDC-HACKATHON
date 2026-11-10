# Draft integration contracts

These JSON shapes are provisional and require workstream owner review before integration.

Candidate profile: `{ "candidate_id": "string", "career_track": "hardware|software|business|product", "resume_text": "string", "projects": [], "skills": [], "preferences": {} }`.

Research output: `{ "job_id": "string", "track": "hardware|software|business|product", "title": "string", "company": "string", "required_skills": [], "preferred_skills": [], "eligibility_requirements": [], "source_url": "string", "retrieved_at": "ISO-8601 UTC" }`.

Depth API: `POST /depth/evaluations` accepts multipart form fields `project_id`, `career_track`, optional `repository_url`, `project_text`, `mode` (`mock|live|codex`) and repeated `files`. It returns `202 {evaluation_id, status}`. `GET /depth/evaluations/{id}` returns status and result/error. `POST /depth/evaluations/{id}/answers` accepts `{ "answers": [{"question_id":"string", "answer":"string"}] }`, returns `202`, and creates a new revision. Poll GET for completion.

Depth result: `{ "project_id": "string", "repository_url": "string|null", "commit_sha": "string|null", "project_summary": "string", "summary_evidence_ids": [], "architecture_summary": "string", "architecture_evidence_ids": [], "depth_score": "number|null", "confidence": "low|medium|high|unassessed", "dimensions": {"conceptual": null, "implementation": null, "systems": null, "tradeoffs": null, "validation": null}, "demonstrated_skills": [], "unverified_skills": [], "evidence": [], "limitations": [], "follow_up_questions": [], "evaluation_mode": "mock|live|codex", "revision": 0 }`. Each non-null dimension is `{ "score": 0-4, "evidence_ids": [] }`; each evidence item contains `id`, `source_type` (`repository|document|claim|answer`), `location`, and `excerpt`. Self-reported claims cannot alone establish implementation, validation, or demonstrated skills. Revisions preserve prior results in `history`.

Judge output: `{ "job_id": "string", "candidate_id": "string", "fit_score": null, "confidence": "unassessed", "eligibility": "unknown", "pro_arguments": [], "anti_arguments": [], "skill_gaps": [], "recommendations": [], "verdict": "pending" }`. Eligibility is separate from weighted fit; fit is not a hiring probability.
