# Phased Implementation and Suggested Repo Structure

## Phase 0: Project Setup + Dataset Pipeline (Foundation)
**Deliverables**
- Hugging Face dataset download + local caching.
- Preprocessing script that transforms raw dataset rows into a normalized restaurant dataset.
- Define and document the preprocessed schema:
  - `restaurant_id`, `name`, `location`, `cuisine`, `rating`, `cost_bucket`, etc.
- Save the preprocessed artifact to disk for fast startup (e.g., Parquet).

**Acceptance Criteria**
- Running the preprocessing script produces a valid artifact.
- Schema mapping is deterministic and logged.

## Phase 1: Candidate Filtering + LLM Ranking (MVP)
**Deliverables**
- Implement `POST /recommendations`.
- Implement:
  - preference parsing/normalization
  - candidate selection with hard filters + top `K`
  - prompt building
  - LLM call requesting structured JSON
  - validation + response formatting
- Output must include:
  - name, cuisine, rating, estimated cost bucket, explanation

**Acceptance Criteria**
- For a sample set of requests, API returns valid JSON and explanations.
- Explanations do not claim attributes outside the candidate data.

## Phase 2: Robustness + Better Candidate Quality
**Deliverables**
- Add schema validation and automatic "repair" flow for LLM JSON parsing.
- Add fuzzy matching for cuisine/location if dataset has inconsistent values.
- Improve budget mapping to cost buckets (quantiles).
- Add caching for:
  - dataset artifact load
  - candidate selections (by normalized preference key)
  - LLM responses (optional TTL)

**Acceptance Criteria**
- Reduced parse failures and fewer fallback paths.
- More consistent ranking ordering.

## Phase 3 (Optional): Retrieval-Augmented Candidate Selection
**Deliverables**
- Create embeddings over restaurants (based on available text fields).
- Retrieve top semantic candidates and merge with hard-filtered candidates.
- Use hybrid scoring (filters + similarity) to form final top `K`.

**Acceptance Criteria**
- Improved recommendations for partial or varied user inputs.

## Suggested Folder Structure (implementation-agnostic)
Use this as a baseline regardless of whether you choose FastAPI, Flask, Express, etc.

```text
.
├─ docs/
│  └─ architecture/
│     ├─ 00-architecture-overview.md
│     ├─ 01-requirements-and-design-decisions.md
│     ├─ 02-data-flow-and-components.md
│     ├─ 03-api-contracts-and-llm-contract.md
│     └─ 04-phased-implementation-and-repo-structure.md
├─ data/
│  └─ processed/                # preprocessed restaurant dataset artifacts
├─ scripts/
│  ├─ ingest_dataset.py        # download raw dataset
│  └─ preprocess_restaurants.py
├─ src/
│  ├─ zomato_ai/
│  │  ├─ phase1/ … phase2/ … phase3/ …
│  │  └─ phase4/                 # FastAPI app (`app.py`, `schemas.py`, `paths.py`)
├─ frontend/
│  ├─ package.json               # Next.js app
│  ├─ src/app/page.tsx           # Preferences screen
│  ├─ src/app/results/page.tsx   # Personalized recommendations screen
│  └─ src/app/globals.css        # Editorial design system styles
│  ├─ api/                       # (legacy sketch; this repo uses phase4)
│  │  └─ routes_recommendations.(py/js)
│  ├─ domain/
│  │  ├─ models.(py/ts)        # UserPreferences, RestaurantRecord, Recommendation
│  │  └─ schemas.(py/ts)       # request/response validation schemas
│  ├─ services/
│  │  ├─ recommendation_service.(py/ts)
│  │  ├─ candidate_selector.(py/ts)
│  │  ├─ prompt_builder.(py/ts)
│  │  ├─ llm_client.(py/ts)
│  │  └─ output_validator.(py/ts)
│  └─ infrastructure/
│     ├─ dataset_loader.(py/ts)
│     ├─ cache.(py/ts)
│     └─ observability.(py/ts)
└─ README.md
```

## Implementation Notes (What to decide early)
1. Gemini model choice for Phase 3 (for example, `gemini-1.5-flash` or equivalent current model).
2. `.env` handling for `GEMINI_API_KEY` (local development and deployment secrets management).
3. Runtime framework (FastAPI recommended for Python, but architecture is portable).
4. Preprocessing schema and cost bucket mapping strategy.
5. Candidate limit `K` and explanation length targets.

