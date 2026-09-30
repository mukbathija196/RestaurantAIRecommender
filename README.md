# Zomato AI Recommendation (Milestone 1)

## Phase 1 (Implemented): Foundation, dataset contract, and catalog

### Setup
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 1) Ingest dataset (optional snapshot)
```bash
python scripts/ingest_dataset.py
```

### 2) Preprocess into canonical contract + write processed artifact
```bash
python scripts/preprocess_restaurants.py
```

This creates:
- `data/processed/<version>/restaurants.parquet`
- `data/processed/<version>/metadata.json`

### 3) Query the catalog (acceptance criteria)
```bash
python scripts/query_catalog.py --location "BTM" --location-match exact --min-rating 4.0 --limit 10
```

## Phase 2 (Implemented): Preference model + deterministic filtering

### Select deterministic candidates (top K)
```bash
source .venv/bin/activate
python scripts/select_candidates.py \
  --location "BTM" \
  --budget medium \
  --cuisine "Italian" \
  --min-rating 4.0 \
  --location-match exact \
  --top-k 10
```

### Run Phase 2 tests
```bash
source .venv/bin/activate
python -m unittest discover -s tests -p "test_*.py" -v
```

## Phase 3 (Implemented): Gemini LLM + prompt contract + orchestration

### Configure Gemini
1. Copy `.env.example` to `.env` in the project root.
2. Set `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey).
3. Optional: set `GEMINI_MODEL` (default: `gemini-2.5-flash`).

### End-to-end recommendations (orchestrator)
```bash
source .venv/bin/activate
python scripts/recommend.py \
  --location "BTM" \
  --budget medium \
  --cuisine "Italian" \
  --min-rating 4.0 \
  --location-match exact \
  --limit 10
```

### Dry run (no API key; deterministic fallback only)
```bash
python scripts/recommend.py --dry-run --location "BTM" --budget medium --min-rating 4.0 --location-match exact --limit 5
```

Phase 3 code lives under `src/zomato_ai/phase3/` (`prompt_contract`, `prompt_builder`, `gemini_client`, parser/validator, `orchestrator`).

Hardening for flaky JSON: Gemini gets a **strict JSON system instruction**, **JSON MIME type** when supported, a **stricter retry** prompt, **robust JSON extraction** (including prose around JSON), and a **repair** pass before deterministic fallback.

## Phase 4 (Implemented): HTTP API + lightweight web UI

The REST API lives under `src/zomato_ai/phase4/` (`schemas`, `paths`, `app`). A **lightweight web UI** is served at **`/ui/`** (static HTML + `fetch` to `POST /recommendations` on the same origin).

### Run the API server
From the project root (requires `.env` with `GEMINI_API_KEY`, and processed data under `data/processed/` unless you set `DATA_ARTIFACT_PATH`):

```bash
source .venv/bin/activate
PYTHONPATH=src uvicorn zomato_ai.phase4.app:app --reload --host 0.0.0.0 --port 8000
```

- **Web UI:** `http://127.0.0.1:8000/ui/` — form to test end-to-end
- OpenAPI docs: `http://127.0.0.1:8000/docs`
- `GET /ui/options` — UI data (`cities`, `localities_by_city`, cuisines ordered by popularity, `popular_cuisines` top-6, and budget bands in 1000-sized blocks up to 5000)
- `POST /recommendations` — body matches `RecommendRequest` in `src/zomato_ai/phase4/schemas.py`
- `GET /health` — liveness
- Optional env: `DATA_ARTIFACT_PATH` (explicit parquet/csv/jsonl path), `CORS_ORIGINS` (comma-separated or `*` for dev), `RECOMMENDATIONS_DRY_RUN=true` (Gemini fallback only; no key required)

### Example request
```bash
curl -s -X POST http://127.0.0.1:8000/recommendations \
  -H "Content-Type: application/json" \
  -d '{"city":"Bengaluru","locality":"BTM","budget_min":500,"budget_max":1500,"cuisines":["Italian"],"min_rating":4.0,"location_match":"exact","limit":5}'
```

### Next.js editorial frontend (2-page UI)
Design-driven frontend lives in `frontend/` and mirrors the Stitch mockups:
- `/` — preferences form screen
- `/results` — personalized matches screen

Run locally (requires Node.js 18+):
```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

## Canonical restaurant contract
See `src/zomato_ai/phase1/schema.py` and `docs/architecture/07-phase-wise-architecture.md`.
