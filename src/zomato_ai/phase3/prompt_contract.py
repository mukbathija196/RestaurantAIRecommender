from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

# Bump when prompt instructions change materially (cache keys / debugging).
PROMPT_VERSION = "3"

# Passed to Gemini as system_instruction (strict JSON contract).
JSON_SYSTEM_INSTRUCTION = """
You are a backend component that outputs machine-readable JSON only.

Hard rules:
- Output exactly ONE JSON object. No markdown. No code fences. No prose before or after.
- Do not wrap the JSON in backticks.
- The JSON must match this shape:
  {"recommendations":[{"rank":<int>,"restaurant_id":<string>,"explanation":<string>}]}
- Every restaurant_id MUST be copied exactly from the provided candidate list.
- Explanations must only reference fields given for each candidate (name, location, cuisine, dish_liked, rating, cost_bucket).
- rank must start at 1 and be unique and contiguous for the items you return.
""".strip()

MAX_CANDIDATES_IN_PROMPT = 30
MAX_NAME_LEN = 80
MAX_CUISINE_LEN = 200
MAX_EXPLANATION_LEN = 400


class CandidateForPrompt(BaseModel):
    restaurant_id: str
    name: str
    location: str
    cuisine: str
    dish_liked: str
    rating: float
    cost_bucket: str


class LLMRecommendationRow(BaseModel):
    rank: int = Field(..., ge=1)
    restaurant_id: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1, max_length=MAX_EXPLANATION_LEN)


class LLMRecommendationPayload(BaseModel):
    recommendations: List[LLMRecommendationRow]


GROUNDING_RULES = """
Grounding rules:
- Only discuss restaurants whose IDs appear in the candidate list.
- Base explanations on the provided fields: name, location, cuisine, dish_liked, rating, cost_bucket.
- Do not invent addresses, prices in INR, or amenities not in the data.
- If the user asked for extra preferences you cannot verify from the data, say you matched on available signals (rating/cuisine/cost/location) only.
""".strip()
