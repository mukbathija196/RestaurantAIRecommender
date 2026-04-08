# Phase-wise Architecture (Milestone Plan)

This document reorganizes the project architecture into the requested phases:
- Phase 1 — Foundation, dataset contract, and catalog
- Phase 2 — Preference model and deterministic filtering
- Phase 3 — LLM integration: prompt contract and orchestration
- Phase 4 — Application layer: API and presentation
- Phase 5 — Hardening, observability, and quality

---

## Phase 1 — Foundation, dataset contract, and catalog
### Goal
Create a stable data foundation: a **canonical restaurant schema** (“dataset contract”) and a **catalog** that can be queried efficiently.

### Components
- **`DatasetLoader`**
  - Downloads the Zomato dataset from Hugging Face.
  - Optional: stores a local raw snapshot for repeatability.
- **`RestaurantSchema` (Dataset Contract)**
  - Defines required fields and normalization rules.
- **`Preprocessor`**
  - Transforms raw rows into the canonical schema.
  - Produces a versioned processed artifact.
- **`RestaurantCatalog`**
  - Loads the processed artifact and exposes query primitives (filter by location/cuisine/rating/cost).
  - Optional: builds indexes for fast filtering.

### Canonical Restaurant Contract (minimum)
Store each restaurant with at least:
```json
{
  "restaurant_id": "string",
  "name": "string",
  "location": "string",
  "cuisine": "string | string[]",
  "dish_liked": "string",
  "rating": 4.2,
  "cost_bucket": "low|medium|high"
}
```

### Deliverables
- `scripts/ingest_dataset.*` (download/snapshot)
- `scripts/preprocess_restaurants.*` (normalize + write processed artifact)
- `data/processed/<version>/restaurants.(parquet|jsonl|csv)`
- `docs/` update: document the contract and mappings (this doc + existing contract docs)

### Acceptance Criteria
- Processed artifact generation is deterministic and repeatable.
- A basic “catalog query” can return restaurants filtered by `location` and `min_rating`.

---

## Phase 2 — Preference model and deterministic filtering
### Goal
Turn user inputs into a normalized preference object and select **top K** candidate restaurants deterministically (no LLM yet).

### Components
- **`UserPreferences` (Domain model)**
  - `location`, `budget`, `cuisines[]`, `min_rating`, `extra_preferences[]`
- **`PreferenceNormalizer`**
  - Normalizes casing, cuisine tokens, and location aliases.
  - Maps `budget` → `cost_bucket` strategy.
- **`DeterministicCandidateSelector`**
  - Hard filters:
    - location match
    - cuisine match (exact/contains/fuzzy depending on dataset quality)
    - `rating >= min_rating`
    - `cost_bucket` alignment
  - Soft scoring to select top `K` (e.g., favor higher ratings and better budget alignment).

### Key Contracts
**Input:** `UserPreferencesNormalized`  
**Output:** `CandidateList` with strict fields for downstream prompting:
```json
{
  "candidates": [
    {
      "restaurant_id": "string",
      "name": "string",
      "location": "string",
      "cuisine": "string | string[]",
      "dish_liked": "string",
      "rating": 4.2,
      "cost_bucket": "low|medium|high"
    }
  ]
}
```

### Deliverables
- Domain models and validation schemas (request/response + internal normalized types)
- Deterministic filtering pipeline producing a stable top `K`
- Unit tests for:
  - budget mapping
  - cuisine normalization
  - constraint satisfaction (rating/budget/location/cuisine)

### Acceptance Criteria
- Given the same input preferences and same dataset artifact, top `K` is stable.
- 0% violations for hard constraints (min rating/budget/cuisine/location) after filtering.

---

## Phase 3 — LLM integration: prompt contract and orchestration
### Goal
Use the LLM to **rank** the deterministic candidates and produce **grounded explanations** using a strict JSON contract.

### Provider and key management
- LLM provider for this phase: **Google Gemini**.
- API key source: local `.env`.
- Environment variable name: `GEMINI_API_KEY`.

### Components
- **`PromptContract`**
  - Defines:
    - Candidate schema provided to the LLM
    - Output JSON schema expected back
    - Grounding rules (do not invent attributes)
- **`PromptBuilder`**
  - Converts normalized preferences + candidate list into a prompt.
  - Enforces size limits (truncate long fields, limit `K`).
- **`LLMClient`**
  - Calls Gemini with low temperature for stability.
- **`LLMOutputParser`**
  - Parses JSON output.
- **`LLMOutputValidator`**
  - Validates:
    - required fields present
    - ranks unique and within bounds
    - `restaurant_id` exists in candidate set
  - Repair strategy:
    - one retry with stricter formatting instructions
    - fallback to deterministic ranking if persistent failure

### LLM Output Contract (recommended)
Keep LLM output minimal and join details from candidates in code:
```json
{
  "recommendations": [
    { "rank": 1, "restaurant_id": "string", "explanation": "string" }
  ]
}
```

### Deliverables
- Versioned prompt template(s) + schema definition
- Parser/validator with tests using stored sample responses (good + bad)
- Orchestrator service combining Phase 2 selector + LLM ranker
- `.env` loading for `GEMINI_API_KEY` and startup validation if missing

### Acceptance Criteria
- Output is valid JSON matching schema in ≥ 99% of runs (with retry/repair).
- Explanations are grounded in candidate-provided fields (no contradictory claims).

---

## Phase 4 — Application layer: API and presentation
### Goal
Expose the system to users and present recommendations cleanly.

### Status (this project)
- **Backend (HTTP API): implemented** — FastAPI app in `src/zomato_ai/phase4/` with `POST /recommendations`, `GET /health`, OpenAPI at `/docs`.
- **Presentation layer (web UI): implemented with Next.js** — two-page frontend in `frontend/`:
  - `/` preferences page (editorial form)
  - `/results` personalized matches page
  - UI consumes `GET /ui/options` and `POST /recommendations`.

### Components
- **API Layer**
  - `POST /recommendations` accepting user preferences (`city`, `locality`, numeric budget range, cuisines, rating)
  - `GET /ui/options` exposing data-backed UI options (cities, localities, cuisines, budget bands)
  - request validation + error handling
  - response formatting (include full restaurant fields + explanation)
- **Presentation Layer (choose one)**
  - Next.js web app (`frontend/`) with two pages and client-side API integration
  - optional static UI fallback (`src/zomato_ai/phase4/static/index.html`)

### API Contract (summary)
Request:
```json
{
  "city": "Bengaluru",
  "locality": "BTM",
  "budget_min": 500,
  "budget_max": 1500,
  "cuisines": ["Italian"],
  "min_rating": 4.0
}
```
Response:
```json
{
  "request_id": "uuid-string",
  "recommendations": [
    {
      "rank": 1,
      "restaurant_id": "string",
      "name": "string",
      "cuisine": "string | string[]",
      "dish_liked": "string",
      "location": "string",
      "rating": 4.6,
      "estimated_cost": "low|medium|high",
      "explanation": "string"
    }
  ]
}
```

### Deliverables
- Runnable app entrypoint (API server + optional UI)
- Basic documentation in `README.md` for how to run and call the API

**Done:** API server (`uvicorn zomato_ai.phase4.app:app`) and a Next.js frontend (`frontend/`) modeled from the design system with preferences and personalized-results pages.

### Acceptance Criteria
- A user can input preferences and see top recommendations with explanations.
- Errors are returned with actionable messages (validation errors, no matches, LLM down).

---

## Phase 5 — Hardening, observability, and quality
### Goal
Make it production-ready: measurable, robust, and easy to iterate without regressions.

### Components
- **Caching**
  - processed artifact cache at startup
  - candidate cache keyed by normalized preferences
  - optional LLM response cache (TTL, prompt version key)
- **Observability**
  - latency per stage (filtering vs LLM vs validation)
  - parse/validation failure rates
  - fallback rate
  - cache hit rate
- **Quality Gates**
  - regression tests for prompt/schema changes
  - offline evaluation harness with representative preference cases
  - sanity checks: constraint satisfaction and candidate-ID grounding

### Deliverables
- Metrics + structured logs
- Offline evaluation script and a small benchmark set
- Documented failure modes and fallback behaviors

### Acceptance Criteria
- Stable performance with high cache hit rates on repeated requests.
- Clear dashboards/logs for diagnosing LLM issues (without exposing secrets).
- Low fallback usage and high schema validity in practice.

