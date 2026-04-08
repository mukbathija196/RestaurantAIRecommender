# Caching and Performance

## Why caching is required
Without caching, each request would:
- repeatedly load/download the dataset
- re-filter large candidate pools
- call the LLM for nearly identical preference inputs

This is slow and expensive, and makes results inconsistent under load.

## What to cache
### 1) Preprocessed dataset artifact
Cache the preprocessed restaurant dataset on disk:
- created in Phase 0
- loaded at service startup (or lazily on first request)

Implementation hints:
- Store as Parquet/JSONL for fast read.
- Version the artifact using a deterministic preprocessing config hash.

### 2) Candidate sets
Cache top `K` candidates keyed by normalized preferences:
`cache_key = hash(location, budget_bucket, cuisines[], min_rating_bucket_or_exact)`

Recommendations:
- bucket `min_rating` (e.g., rounding to 0.1) to improve cache hit rate.
- cap cache size (LRU) to bound memory/disk.

### 3) LLM results (optional but helpful)
Cache the final recommendations keyed by:
`cache_key = hash(normalized_preferences, candidate_ids_subset, llm_model, prompt_version)`

Only do this if:
- you can safely treat requests as deterministic enough (low temperature)
- you can tolerate stale recommendations within TTL

## Candidate selection performance
### Indexing strategy
To avoid scanning the entire dataset per request:
- Build indexes during preprocessing:
  - location -> list of restaurant rows
  - cuisine -> list of restaurant rows
  - rating/cost fields indexed or sortable

Then candidate selection does set intersections:
1. Start with location filter results.
2. Intersect with cuisine filter results.
3. Apply rating and budget constraints.
4. Select top `K` by pre-scoring.

### Vectorization (if using Python)
- Use `pandas` for preprocessing.
- During runtime, keep a cached in-memory dataframe or use a lightweight DB (SQLite) depending on dataset size.

## LLM cost and token limits
Control prompt size by:
- limiting to top `K` candidates (e.g., 20-50)
- truncating candidate fields (max length)
- minimizing whitespace and verbose strings
- keeping explanations instruction concise

Suggested generation settings:
- `temperature`: low (0.0-0.3)
- enforce JSON-only output via prompt + validator
- set `llm_model` to the selected **Gemini** model id

### Gemini credentials
- Load Gemini credentials from `.env` with `GEMINI_API_KEY`.
- Do not log the API key or include `.env` in source control.

## Failure handling strategy
1. If LLM JSON parsing fails:
   - retry once with stricter "output-only-json" instructions
2. If schema validation fails:
   - attempt repair prompt ("return JSON that matches schema")
3. If LLM still fails:
   - fallback to deterministic ranking using candidate pre-scores
   - produce short explanations from available attributes (template-based)

## Metrics to collect
- total request latency
- time spent in:
  - candidate selection
  - LLM call
  - validation/repair
- cache hit rate (dataset/candidates/LLM)
- parse failure rate
- fallback rate

