# Evaluation and Observability

## Observability Goals
You need visibility into:
1. How long each stage takes.
2. Where failures occur (prompt parsing vs schema validation).
3. Whether recommendations match constraints.

## Runtime Metrics (recommended)
Stage timing:
- `dataset_load_time_ms`
- `preprocessing_load_time_ms` (if separate)
- `candidate_selection_time_ms`
- `llm_call_time_ms`
- `llm_validation_time_ms`

Failure counters:
- `llm_json_parse_failures_total`
- `llm_schema_validation_failures_total`
- `llm_repair_attempts_total`
- `fallback_recommendations_total`

Caching metrics:
- `candidate_cache_hits_total`, `candidate_cache_misses_total`
- `llm_cache_hits_total`, `llm_cache_misses_total` (if enabled)

Output sanity checks:
- `violates_min_rating_total` (should be 0 after hard filters)
- `violates_budget_total` (should be 0 after budget mapping)
- `candidate_id_mismatch_total` (LLM returned restaurants not in candidate list)

## Offline Evaluation (before/after changes)
Create a small evaluation harness:
1. Prepare a list of representative preference inputs:
   - different locations
   - different cuisines
   - varying min rating thresholds
   - low/medium/high budgets
2. Run the recommender and collect outputs.
3. Evaluate automatically:
   - constraint satisfaction rate (min rating, budget, cuisine match)
   - schema validity rate (JSON parse + validator pass)
   - explanation grounding heuristics:
     - explanation contains the cuisine/location keywords present in candidate fields
     - explanation references rating/cost bucket patterns

## Human-in-the-loop Review (optional)
For a small subset (e.g., 20 cases), manually verify:
- Are top 3 recommendations plausible?
- Do explanations feel user-friendly and not repetitive?
- Are there any obviously incorrect/hallucinated claims?

## Prompt/Contract Regression Testing
Whenever you change the prompt template or output schema:
- re-run:
  - schema validation test suite
  - parse failure test cases
  - ranking format tests (unique ranks, list length)

## Logging Requirements (safe logging)
Log enough to debug without exposing secrets:
- `request_id`
- normalized preferences
- candidate selection summary (counts, selected top `K` IDs)
- validator errors (structured error codes)
- LLM raw response only if you can store it safely (redact sensitive data)
- never log `GEMINI_API_KEY` from `.env`

