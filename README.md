# Restaurant AI Recommender

An AI-powered restaurant recommender for Bengaluru, built on the
[Zomato restaurant dataset](https://huggingface.co/datasets/ManikaSaini/zomato-restaurant-recommendation).
You pick a locality, budget, cuisines and a minimum rating; the app filters and
scores the catalog, then asks Google Gemini to re-rank the best candidates and
explain in plain language why each one fits.

- **Backend:** Python, FastAPI, pandas, Google Gemini
- **Frontend:** Next.js (App Router) + React + TypeScript
- **Data:** ~51k Zomato listings, preprocessed into a versioned Parquet artifact

## How it works

```
User preferences ──► Phase 2: deterministic filter + score ──► top 30 candidates
                                                                   │
                                                                   ▼
          Response ◄── Phase 3: Gemini re-rank + explanations (JSON contract)
                       └─ falls back to the deterministic ranking if the LLM
                          is unavailable or returns invalid output
```

| Phase | Package | What it does |
|---|---|---|
| 1 | `src/zomato_ai/phase1` | Loads the Hugging Face dataset, normalises it into a canonical restaurant schema (`schema.py`), and writes `data/processed/<version>/restaurants.parquet` plus `metadata.json`. |
| 2 | `src/zomato_ai/phase2` | Parses user preferences and deterministically filters (location, budget, cuisine, rating) and scores restaurants to pick the top candidates. |
| 3 | `src/zomato_ai/phase3` | Builds a versioned prompt, calls Gemini, and parses and validates the JSON output. Hardened against flaky JSON with a strict system instruction, JSON MIME type, a stricter retry, robust extraction, and a repair pass before falling back. |
| 4 | `src/zomato_ai/phase4` | FastAPI service exposing the recommender over HTTP, plus a lightweight test UI at `/ui/`. |
| UI | `frontend/` | Two-page Next.js app: a preferences form (`/`) and personalised results (`/results`). |

### Build status

All four phases are implemented end to end:

- **Phase 1:** foundation, dataset contract and catalog
- **Phase 2:** preference model and deterministic filtering
- **Phase 3:** Gemini LLM, prompt contract and orchestration. The code is split
  into `prompt_contract`, `prompt_builder`, `gemini_client`,
  `llm_output_parser`, `llm_output_validator` and `orchestrator`.
- **Phase 4:** HTTP API, the lightweight `/ui/` test page, and the Next.js
  frontend (based on the Stitch mockups in `design/`)

### Canonical restaurant contract

Every phase works on one normalised restaurant record, defined in
[`src/zomato_ai/phase1/schema.py`](src/zomato_ai/phase1/schema.py) and
described in
[`docs/architecture/07-phase-wise-architecture.md`](docs/architecture/07-phase-wise-architecture.md).

Design docs live in [`docs/architecture/`](docs/architecture/) (start with
`00-architecture-overview.md`), and the original brief is in
[`docs/problemstatement.md`](docs/problemstatement.md).

## Repository layout

```
src/zomato_ai/      Python package (phase1 … phase4)
scripts/            CLI entry points for each phase
tests/              unittest suites for phases 2–4
data/processed/     Committed, versioned Parquet artifacts
frontend/           Next.js frontend
docs/               Problem statement and architecture notes
design/             UI mockups the frontend is based on
```

## Quick start

### Prerequisites

- Python 3.9+ (3.11 recommended)
- Node.js 18+ (for the frontend)
- A Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)
  (optional: the app runs without one in dry-run mode)

### 1. Install the backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then set GEMINI_API_KEY
```

### 2. Run the API

Processed data is already committed under `data/processed/`, so you can start
the server straight away:

```bash
PYTHONPATH=src uvicorn zomato_ai.phase4.app:app --reload --host 0.0.0.0 --port 8000
```

- Test UI: http://127.0.0.1:8000/ui/
- OpenAPI docs: http://127.0.0.1:8000/docs

No API key yet? Set `RECOMMENDATIONS_DRY_RUN=true` to skip Gemini and return
the deterministic ranking.

### 3. Run the frontend

```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000.

## Configuration

Set these in `.env` at the repo root (see [`.env.example`](.env.example)) or
in your host's environment.

| Variable | Used by | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | backend | Gemini API key. Required unless dry-run is on. |
| `GEMINI_MODEL` | backend | Override the Gemini model. The default is set in `src/zomato_ai/phase3/env_config.py`. |
| `DATA_ARTIFACT_PATH` | backend | Explicit path to the catalog (`.parquet`, `.csv` or `.jsonl`). Without it, the newest folder under `data/processed/` is used. |
| `CORS_ORIGINS` | backend | Comma-separated allowed origins, or `*` (the default). |
| `RECOMMENDATIONS_DRY_RUN` | backend | `true` to skip Gemini and use the deterministic fallback. |
| `NEXT_PUBLIC_API_BASE_URL` | frontend | Base URL of the API. Read at build time. |

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. |
| `GET` | `/ui/options` | Form data: `cities`, `localities_by_city`, `cuisines` ordered by popularity, the top-6 `popular_cuisines`, and `budget_bands`. |
| `POST` | `/recommendations` | Ranked recommendations with AI explanations. The body is `RecommendRequest`. |
| `GET` | `/ui/` | Lightweight static test page that calls `POST /recommendations` on the same origin. |
| `GET` | `/docs` | OpenAPI (Swagger) docs. |

Request and response models are in
[`src/zomato_ai/phase4/schemas.py`](src/zomato_ai/phase4/schemas.py). Example:

```bash
curl -s -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"city":"Bengaluru","locality":"BTM","budget_min":500,"budget_max":1500,
       "cuisines":["Italian"],"min_rating":4.0,"location_match":"exact","limit":5}'
```

Each recommendation includes `name`, `location`, `cuisine`, `dish_liked`,
`rating`, `estimated_cost` and `explanation`. The `meta` block reports
`used_fallback`, `llm_model` and any `error`, which is the first place to look
if explanations look generic.

## Command-line tools

Each phase can be run on its own from the repo root:

```bash
# Phase 1: download and snapshot the raw dataset (needs Hugging Face access)
python scripts/ingest_dataset.py

# Phase 1: rebuild the processed artifact in data/processed/<version>/
python scripts/preprocess_restaurants.py

# Phase 1: query the catalog
python scripts/query_catalog.py --location "BTM" --location-match exact --min-rating 4.0 --limit 10

# Phase 2: deterministic candidates only
python scripts/select_candidates.py --location "BTM" --budget medium --cuisine "Italian" \
  --min-rating 4.0 --location-match exact --top-k 10

# Phase 3: end-to-end recommendations (needs GEMINI_API_KEY in .env)
python scripts/recommend.py --location "BTM" --budget medium --cuisine "Italian" \
  --min-rating 4.0 --location-match exact --limit 10

# Phase 3: dry run with no API key (deterministic fallback only)
python scripts/recommend.py --dry-run --location "BTM" --budget medium \
  --min-rating 4.0 --location-match exact --limit 5
```

Activate the virtualenv first (`source .venv/bin/activate`).
`preprocess_restaurants.py` writes `restaurants.parquet` and `metadata.json`
into a new `data/processed/<version>/` folder.

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v
```

The API tests use FastAPI's `TestClient`, which needs `httpx`
(`pip install httpx`).

## Deployment

The recommended setup is the frontend on **Vercel** and the backend on
**Render** (or any host that runs a long-lived Python process). The backend's
dependencies are too large for a Vercel Python function, and it loads the full
catalog into memory at startup.

- **Backend (Render web service):** build with `pip install -r requirements.txt`,
  start with `PYTHONPATH=src uvicorn zomato_ai.phase4.app:app --host 0.0.0.0 --port $PORT`.
  Set `GEMINI_API_KEY`, and pin `DATA_ARTIFACT_PATH` to a specific folder under
  `data/processed/` because a fresh clone gives every folder the same
  timestamp. Once the frontend is live, set `CORS_ORIGINS` to its URL.
- **Frontend (Vercel):** set the project's Root Directory to `frontend` and
  `NEXT_PUBLIC_API_BASE_URL` to the backend URL (no trailing slash). Redeploy
  after changing it, since it is baked in at build time.
