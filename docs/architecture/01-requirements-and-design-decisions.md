# Requirements and Design Decisions

## Functional Requirements (from `docs/problemstatement.md`)
1. Load and preprocess the Zomato dataset from Hugging Face.
2. Accept user preferences:
   - `location` (e.g., Delhi, Bangalore)
   - `budget` (low/medium/high)
   - `cuisine` (e.g., Italian, Chinese)
   - `minimum rating`
   - optional extra preferences (e.g., family-friendly, quick service)
3. Filter and prepare restaurant data relevant to the user input.
4. Use an LLM to:
   - rank restaurants
   - generate an explanation for each recommendation
5. Display results including:
   - Restaurant name
   - Cuisine
   - Rating
   - Estimated cost
   - AI-generated explanation

## Non-Functional Requirements
1. Reliability of outputs
   - LLM responses must be validated against a strict schema.
2. Performance
   - Dataset loading/preprocessing should not happen per request.
   - Candidate sets and LLM results should be cached where safe.
3. Safety / robustness
   - LLM should not hallucinate missing structured fields.
   - If validation fails, retry with corrected instructions or fall back to deterministic scoring.
4. Maintainability
   - Clear module boundaries and contracts between preprocessing, candidate selection, prompt building, and LLM parsing.

## Core Design Decisions
### 1) Hybrid selection: deterministic candidate selection + LLM ranking
Reason:
- LLMs are expensive and can be less deterministic for hard filters (budget/rating).
- Pre-filtering improves both relevance and reduces prompt size.

### 2) Structured LLM outputs (JSON) with validation
Reason:
- You need stable rank lists and explanations that map to candidates.
- JSON output makes it possible to enforce required fields and constraints.

### 3) Prompt grounding using a fixed candidate schema
Reason:
- The LLM should only explain using candidate-provided attributes (rating/cuisine/location/cost bucket).
- Prevents explanations that contradict the dataset.

## Preference Normalization
User preferences vary in spelling and granularity. Normalize early:
1. Location:
   - case fold (`"delhi"` -> `"Delhi"`)
   - optionally support synonyms/aliases (config file)
2. Cuisine:
   - case fold
   - optionally tokenize and fuzzy-match cuisines
3. Budget:
   - map `low|medium|high` to dataset cost buckets using quantiles or a fixed heuristic.
4. Minimum rating:
   - numeric threshold (float)

## Candidate Scoring (Pre-LLM)
Before calling the LLM, score candidates for candidate selection:
- Hard filters:
  - location match
  - cuisine match (or cuisine containment)
  - rating >= minRating
  - cost/budget match
- Soft scoring (to pick top `K`):
  - rating score (e.g., normalize to 0-1)
  - cuisine relevance score (exact match > partial match)
  - budget alignment score
  - tie-breakers: frequency of cuisine in candidate, etc.

## Extra Preferences Handling (Initial Strategy)
Initially treat extra preferences as heuristic tags unless the dataset contains relevant fields.
Examples:
- `family-friendly`: use heuristics if dataset has "zomato liked restaurants"/"family/children" signals (often missing), otherwise ask the LLM to infer only from available attributes.
- `quick service`: similarly, if no serving-speed field exists, limit claims to generic language and prefer restaurants with higher ratings / popularity proxy if available.

In later phases, extra preferences can be handled by:
- embedding-based retrieval
- mapping tags to dataset text fields if those fields exist

## LLM Behavior Requirements
The LLM must:
1. Rank candidates by "preference fit" while respecting constraints already applied.
2. Generate one short explanation per candidate that references at least:
   - matching cuisine and/or location
   - rating and/or cost bucket
   - any extra preference that can be supported by data (or clearly framed as "based on available attributes")
3. Output valid JSON matching the contract.

## Gemini configuration (Phase 3)
- Provider: **Google Gemini**.
- API key source: `.env` file.
- Environment variable: `GEMINI_API_KEY`.
- Keep `.env` local-only and excluded from commits.

