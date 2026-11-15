# Matching v4 and Paralegal v2

This replaces exact-term matching in the source-checked Judge path (`local-trial-v4`). The legacy path (`MATCHER=legacy`, or no Gemini key) is unchanged and still used for non-source-checked jobs.

## Why scores moved between runs (80 / 60 / 50 / 62)

1. Credit depended on the label Depth chose for a demonstrated skill, and Depth is a model that varies run to run.
2. The Judge scored against evidence already trimmed to what the Lawyer prompt selected, so adding a repository changed which excerpts survived.
3. Exact term matching meant a paraphrase of the same experience scored differently from the keyword.

## What changed

| Problem | Fix | Where |
|---|---|---|
| Depth label variance | Score against the raw cited excerpts (`full_evidence`), not Depth's skill labels; Depth model calls are cached by content hash (`DEPTH_EVAL_CACHE=0` disables) | `review.py`, `depth/evaluation.py` |
| Portfolio-size sensitivity | Scoring sees all evidence; only the Lawyer prompt is trimmed | `review.py` |
| Exact-term matching | Hybrid retrieval (Gemini embeddings + ontology concepts + lexical) proposes candidates; a temperature-0 verifier must quote the supporting words verbatim or the verdict is void | `matching.py`, `ontology.py` |
| Run-to-run variance | Retrieval embeddings and verifier verdicts are cached by content hash; fixed evidence reproduces the same score | `matching.py` (`MATCH_CACHE_PATH`) |
| Guessed 2:1 weights and 0.5 claim credit | Graded strengths and a depth-asked-for bar (below) | `matching.py` |
| Fixed-vocabulary paralegal | Claim-level extraction with verbatim-span validation, skills/coursework lines always captured, facts (graduation date etc.) extracted | `paralegal.py` |
| Free-tier rate limits | Per-key, per-model limiter (13/min), rotating keys | `gemini_client.py` |

## Scoring rule

Evidence strength (source, relationship, specificity):

| Evidence | Strength |
|---|---|
| Inspected repository/document shows it | 1.0 |
| Inspected artifact shows a transferable neighbour (Verilog for SystemVerilog) | 0.6 |
| Résumé claim: specific action with a stated measurable result | 0.7 |
| Résumé claim: specific action, tool or artifact | 0.6 |
| Résumé claim: coursework or named skill with detail | 0.4 |
| Bare entry in a skills list | 0.3 |
| Claim of a transferable neighbour | 0.25 |
| Negated, planned or "learning" | 0 |

Each requirement carries `expected_depth` extracted from the posting wording: familiarity 0.4, working 0.7 (default for required), advanced 1.0. Coverage = `min(1, strength / expected)`. A posting that asks for "familiarity" is fully met by coursework; "strong" or "extensive" is not.

Score = 100 × (0.8 × mean required coverage + 0.2 × mean preferred coverage); a missing class passes its weight to the other. Required and preferred are weighted by class, not by item count, so a posting with many preferred bullets cannot dominate. The response also carries `score_range.low`, the score with transferable-only credit removed.

Design rationale for new graduates and interns: coursework, class projects, hackathons, clubs, research and open source count as real experience; a missing internship is never a gap; depth is judged against what the posting asks, not an expert bar; skills-list keywords are the weakest evidence, so stuffing is worth little; eligibility facts are shown as `candidate_reported_unverified` and never add points.

**These strengths are documented priors, not fitted values.** No human-labeled gold set exists yet.

## Verification

- `tests/web/test_matching.py`: ontology equivalence, negation, void unquoted verdicts, cache determinism, depth-asked-for, artifact vs claim, order/duplicate/irrelevant-evidence invariance, monotonicity, required vs preferred, paralegal span validation.
- `scripts/calibration/run_stress.py`: synthetic applicants at eight intended levels (cracked, strong, solid, average, weak, keyword-stuffed, learning-only, irrelevant) across HW, CS and PM against two intern job descriptions per track, repeated with fresh caches. Results: `reports/calibration/stress.json` and `docs/calibration-results.md`. Levels are synthetic by construction and test monotonicity, stuffing and negation resistance and rerun stability. They do not show agreement with recruiters.
- `scripts/calibration/gold.py`: blind labeling sheets, Cohen's kappa between reviewers, accuracy against consensus, false-credit and missed-credit rates, and score-vs-rating Spearman. Calibration against humans stays **pending** until reviewers fill `labels-<name>.jsonl`.

## Operating notes

- Set `GEMINI_API_KEY` (and optionally `GEMINI_API_KEY_2`) in the server environment only. Free tier allows 15 requests per minute per key and model; spread roles across models with `RESEARCH_GEMINI_MODEL`, `PARALEGAL_GEMINI_MODEL`, `MATCH_GEMINI_MODEL`.
- `MATCHER=legacy` and `PARALEGAL=legacy` restore the previous behaviour. Changing the model or `MATCHER_VERSION` invalidates cached verdicts.
- Remaining limits: the ontology is a recall aid with about 50 concepts; the verifier is a model and can still be wrong, which is why every credit needs a verbatim quote and why gold-set measurement is the next step.

## Known open issue (at merge time)

Fresh-cache reruns of the synthetic stress set differed by a mean of 17 points (max 100; 71% of pairs within 5) in the last measured run, because verdicts, paralegal extraction and requirement extraction are re-queried by the model when caches are empty. Reruns with warm caches are identical. Level ordering, stuffing and negation checks passed in pass 1. `reports/calibration/stress*.json` hold the raw numbers; this is not yet fixed and no human calibration exists.
