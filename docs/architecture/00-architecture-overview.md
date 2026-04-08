# Architecture Overview (Zomato-Style AI Restaurant Recommendations)

## Purpose
Build an AI-powered restaurant recommendation service inspired by Zomato:
1. Ingest and preprocess a real-world restaurant dataset (Zomato dataset from Hugging Face).
2. Accept user preferences (location, budget, cuisine, minimum rating, and optional extra preferences).
3. Filter and rank candidate restaurants using an LLM.
4. Return top recommendations with clear, human-like explanations.

## Phase-wise plan
For a phase-wise architecture aligned to the milestone phases, see `docs/architecture/07-phase-wise-architecture.md`.

## LLM provider and secrets
- Phase 3 uses **Google Gemini** for ranking and explanation generation.
- The Gemini API key is loaded from a local `.env` file via `GEMINI_API_KEY`.
- `.env` must not be committed to version control.

## High-level Approach
Use a **hybrid** architecture:
- **Deterministic candidate selection** (filters + scoring heuristics) to reduce the search space.
- **LLM ranking + explanation** to produce natural-language, user-tailored reasons.

This reduces prompt size, improves relevance, and makes output schema more reliable.

## Key Design Goals
- Correctness: recommendations must respect user constraints (location/cuisine/min rating/budget).
- Explainability: LLM explanations must be grounded in the provided candidate attributes.
- Reliability: enforce **structured outputs** (JSON) and validate responses.
- Performance: cache expensive steps (dataset load/preprocessing, candidate sets, LLM results).
- Iterability: architecture should support incremental improvements across phases.

## Major Runtime Components
1. **Data Ingestion & Preprocessing**
   - Download the dataset from Hugging Face.
   - Extract a consistent restaurant schema (name, location, cuisine, rating, cost/bucket, etc.).
   - Normalize values (case folding, country/city mappings if present, cost buckets).
2. **Recommendation Service**
   - Parse user input into a normalized preference object.
   - Select a limited set of candidates (top `K`) via hard filters and lightweight ranking.
   - Build an LLM prompt containing user preferences + candidate restaurant records.
   - Call the LLM and request a structured JSON response.
   - Validate/repair the LLM output and format the final response.
3. **API / Interface Layer**
   - Provide an endpoint to accept preferences and return ranked recommendations.
   - **Implemented backend:** FastAPI HTTP API (`POST /recommendations`) in `src/zomato_ai/phase4/`.
   - **Implemented frontend:** Next.js app in `frontend/` with:
     - `/` editorial preferences page
     - `/results` personalized recommendations page
     - data flow via `GET /ui/options` and `POST /recommendations`.
4. **Observability**
   - Track failures (prompt parse issues, validation failures), latency per stage, and basic quality checks.

## Non-Goals for Milestone 1
- Perfect personalization using historical user behavior (no user profiles needed initially).
- Fully automated restaurant ingestion pipelines with continuous updates.
- Complex multi-turn conversational recommendation flows (single request is enough).

## Assumptions
- The dataset contains (or can be mapped to) fields for name, cuisine, location, rating, and cost/price proxy.
- LLM outputs can be constrained to JSON and validated with deterministic rules.

