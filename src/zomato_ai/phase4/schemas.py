from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


Budget = Literal["low", "medium", "high"]
LocationMatch = Literal["exact", "contains"]


class RecommendRequest(BaseModel):
    city: Optional[str] = None
    locality: Optional[str] = None
    location: Optional[str] = None
    budget: Optional[Budget] = None
    budget_min: Optional[float] = Field(None, ge=0.0)
    budget_max: Optional[float] = Field(None, ge=0.0)
    cuisines: List[str] = Field(default_factory=list)
    min_rating: float = Field(0.0, ge=0.0, le=5.0)
    extra_preferences: List[str] = Field(default_factory=list)
    location_match: LocationMatch = "contains"
    limit: int = Field(10, ge=1, le=50)


class RecommendationItem(BaseModel):
    rank: int
    restaurant_id: str
    name: Optional[str] = None
    location: Optional[str] = None
    cuisine: Optional[str] = None
    dish_liked: Optional[str] = None
    rating: Optional[float] = None
    estimated_cost: Optional[str] = None
    explanation: str


class RecommendMeta(BaseModel):
    candidate_count: int
    total_after_filters: int
    used_fallback: bool
    llm_model: str
    prompt_version: str
    error: Optional[str] = None


class RecommendResponse(BaseModel):
    request_id: str
    recommendations: List[RecommendationItem]
    meta: RecommendMeta


class UiOptionsResponse(BaseModel):
    cities: List[str]
    localities_by_city: Dict[str, List[str]]
    cuisines: List[str]
    popular_cuisines: List[str]
    budget_bands: Dict[str, Dict[str, Optional[float]]]
