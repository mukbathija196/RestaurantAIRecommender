from __future__ import annotations

from typing import List, Set, Tuple

import pandas as pd
from pydantic import ValidationError

from zomato_ai.phase3.prompt_contract import LLMRecommendationPayload


def validate_llm_payload(
    data: dict,
    *,
    allowed_ids: Set[str],
    max_rank: int,
) -> Tuple[LLMRecommendationPayload, List[str]]:
    """
    Returns validated payload and a list of non-fatal warnings.
    """
    warnings: List[str] = []
    try:
        payload = LLMRecommendationPayload.model_validate(data)
    except ValidationError as e:
        raise ValueError(f"Schema validation failed: {e}") from e

    if not payload.recommendations:
        raise ValueError("recommendations is empty")

    ranks = [r.rank for r in payload.recommendations]
    if len(set(ranks)) != len(ranks):
        raise ValueError("duplicate ranks in recommendations")

    for r in payload.recommendations:
        if r.rank < 1 or r.rank > max_rank:
            raise ValueError(f"rank {r.rank} out of bounds (1..{max_rank})")
        if r.restaurant_id not in allowed_ids:
            raise ValueError(f"restaurant_id not in candidate set: {r.restaurant_id!r}")

    return payload, warnings


def dataframe_by_id(candidates_df: pd.DataFrame) -> dict:
    """Map restaurant_id -> row dict."""
    out = {}
    for _, row in candidates_df.iterrows():
        rid = str(row.get("restaurant_id", "")).strip()
        if rid:
            out[rid] = row.to_dict()
    return out
