from __future__ import annotations

import math
from typing import Any, List, Optional

from pydantic import BaseModel, Field

# Bump when prompt instructions change materially (cache keys / debugging).
PROMPT_VERSION = "4"

# Passed to Gemini as system_instruction (strict JSON contract).
JSON_SYSTEM_INSTRUCTION = """
You are a backend component that outputs machine-readable JSON only.

Hard rules:
- Output exactly ONE JSON object. No markdown. No code fences. No prose before or after.
- Do not wrap the JSON in backticks.
- The JSON must match this shape:
  {"recommendations":[{"rank":<int>,"restaurant_id":<string>,"explanation":<string>}]}
- Every restaurant_id MUST be copied exactly from the provided candidate list.
- Explanations must only reference fields given for each candidate (name, location, cuisine, dish_liked, rating, cost_bucket, cost_for_two).
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
    cost_for_two: Optional[float] = None


class LLMRecommendationRow(BaseModel):
    rank: int = Field(..., ge=1)
    restaurant_id: str = Field(..., min_length=1)
    explanation: str = Field(..., min_length=1, max_length=MAX_EXPLANATION_LEN)


class LLMRecommendationPayload(BaseModel):
    recommendations: List[LLMRecommendationRow]


GROUNDING_RULES = """
Grounding rules:
- Only discuss restaurants whose IDs appear in the candidate list.
- Base explanations on the provided fields: name, location, cuisine, dish_liked, rating, cost_bucket, cost_for_two.
- cost_for_two is the approximate cost for two people in INR; you may quote it, but do not invent other prices, addresses, or amenities not in the data.
- If the user asked for extra preferences you cannot verify from the data, say you matched on available signals (rating/cuisine/cost/location) only.
""".strip()


def cost_for_two_or_none(value: Any) -> Optional[float]:
    """Numeric cost for two, or None when missing (older artifacts have no such column)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def format_estimated_cost(row: Any) -> Optional[str]:
    """Display string for a candidate's cost: actual INR when known, else the cost bucket."""
    cost = cost_for_two_or_none(row.get("cost_for_two"))
    if cost is not None:
        return f"₹{cost:,.0f} for two"
    bucket = row.get("cost_bucket")
    return str(bucket) if bucket is not None else None
