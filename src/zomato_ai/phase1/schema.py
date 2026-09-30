from __future__ import annotations

from typing import List, Literal, Optional, Sequence, Union

from pydantic import BaseModel, Field


CostBucket = Literal["low", "medium", "high"]


class RestaurantRecord(BaseModel):
    """
    Canonical restaurant contract used across the project.

    This is intentionally minimal to support Phase 1 catalog + later phases.
    """

    restaurant_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    cuisine: Union[str, List[str]] = Field(...)
    dish_liked: Optional[str] = None
    rating: float = Field(..., ge=0.0, le=5.0)
    cost_bucket: CostBucket
    cost_for_two: Optional[float] = Field(None, ge=0.0)


class PreprocessConfig(BaseModel):
    dataset_name: str = "ManikaSaini/zomato-restaurant-recommendation"
    dataset_split: str = "train"
    output_format: Literal["parquet", "jsonl", "csv"] = "parquet"
    cost_bucket_quantiles: Sequence[float] = (0.33, 0.66)

