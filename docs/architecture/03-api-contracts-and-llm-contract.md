# API Contracts and LLM Contract

## Recommendation API
### Implementation
Phase 4 exposes this contract via **FastAPI** (`src/zomato_ai/phase4/app.py`, `schemas.py`). See `GET /docs` when the server is running.

### Endpoint
`POST /recommendations`

### Request Body (JSON)
```json
{
  "location": "Delhi",
  "budget": "low",
  "cuisines": ["Italian", "Chinese"],
  "min_rating": 4.2,
  "extra_preferences": ["family-friendly", "quick-service"]
}
```

### Response Body (JSON)
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
      "rating": 4.7,
      "estimated_cost": "low|medium|high",
      "explanation": "string"
    }
  ],
  "meta": {
    "candidate_count": 42,
    "total_after_filters": 100,
    "used_fallback": false,
    "llm_model": "gemini-*-model-name",
    "prompt_version": "3",
    "error": null
  }
}
```

Request fields also include optional `location_match` (`exact` | `contains`, default `contains`) and `limit` (1–50, default 10).

## Gemini provider setup
- LLM provider for Phase 3: **Google Gemini**.
- API key is read from `.env` via `GEMINI_API_KEY`.
- Validate at startup that `GEMINI_API_KEY` is present; fail fast if missing.

## Internal LLM Input/Output Contracts

### LLM Input to Provide (conceptual)
- `normalized_user_preferences`
- `candidates[]` (top `K`) using the prompt candidate schema
- `output schema` instructions

### LLM Output Contract (strict JSON)
The LLM must output **JSON only** (no markdown) that validates to:
```json
{
  "recommendations": [
    {
      "rank": 1,
      "restaurant_id": "string",
      "explanation": "string"
    }
  ]
}
```

#### Explanation Constraints (to avoid hallucination)
- The explanation must refer to candidate-provided attributes:
  - cuisine match
  - dish liked signals (when available)
  - rating strength
  - location match
  - cost bucket alignment
- If extra preferences cannot be supported by available fields, the explanation should be framed as:
  - "Based on available data, this is likely to match your preferences because..."
  - Avoid claiming unseen attributes as facts.

## Prompt Template (high level)
1. System message:
   - role: recommendation ranker
   - strict requirement: output valid JSON only
2. User message:
   - user preferences
   - candidate list (structured)
   - explicit schema and ranking rules

### Ranking Rules
The LLM should rank by:
- preference fit
- rating quality (>= `min_rating` already satisfied via filters, but still used for ordering)
- budget/cost alignment

