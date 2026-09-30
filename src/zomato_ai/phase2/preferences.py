from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


Budget = Literal["low", "medium", "high"]


class UserPreferences(BaseModel):
    location: str = ""
    budget: Budget
    allowed_cost_buckets: Optional[List[Budget]] = None
    # Cost-for-two range in INR. When set and the catalog has `cost_for_two`,
    # Phase 2 filters on actual cost instead of the coarse cost buckets.
    budget_min: Optional[float] = Field(None, ge=0.0)
    budget_max: Optional[float] = Field(None, ge=0.0)
    cuisines: List[str] = Field(default_factory=list)
    min_rating: float = Field(0.0, ge=0.0, le=5.0)
    extra_preferences: List[str] = Field(default_factory=list)


class UserPreferencesNormalized(BaseModel):
    location: str
    location_norm: Optional[str] = None
    budget: Budget
    allowed_cost_buckets: List[str]
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    cuisines: List[str]
    cuisines_norm: List[str]
    min_rating: float
    extra_preferences: List[str]
    extra_preferences_norm: List[str]
    location_match_mode: Literal["exact", "contains"] = "contains"


class PreferenceNormalizer:
    """
    Normalizes user preferences and maps budget to allowed cost buckets.
    """

    _LOCATION_ALIASES = {
        "btm layout": "btm",
        "koramangala": "koramangala",
        "indira nagar": "indiranagar",
    }

    _BUDGET_TO_COST_BUCKETS = {
        "low": ["low"],
        "medium": ["medium"],
        "high": ["high"],
    }

    @classmethod
    def normalize(
        cls, prefs: UserPreferences, location_match_mode: Optional[str] = None
    ) -> UserPreferencesNormalized:
        loc = prefs.location.strip()
        loc_norm = cls._normalize_location(loc) if loc else None

        cuisines = [c.strip() for c in prefs.cuisines if c.strip()]
        cuisines_norm = [cls._normalize_token(c) for c in cuisines]
        extras = [x.strip() for x in prefs.extra_preferences if x.strip()]
        extras_norm = [cls._normalize_token(x) for x in extras]

        mode = location_match_mode if location_match_mode in {"exact", "contains"} else "contains"

        allowed_buckets = (
            prefs.allowed_cost_buckets
            if prefs.allowed_cost_buckets is not None
            else cls._BUDGET_TO_COST_BUCKETS[prefs.budget]
        )

        budget_min, budget_max = prefs.budget_min, prefs.budget_max
        if budget_min is not None and budget_max is not None and budget_max < budget_min:
            budget_min, budget_max = budget_max, budget_min

        return UserPreferencesNormalized(
            location=loc,
            location_norm=loc_norm,
            budget=prefs.budget,
            allowed_cost_buckets=allowed_buckets,
            budget_min=budget_min,
            budget_max=budget_max,
            cuisines=cuisines,
            cuisines_norm=cuisines_norm,
            min_rating=float(prefs.min_rating),
            extra_preferences=extras,
            extra_preferences_norm=extras_norm,
            location_match_mode=mode,
        )

    @classmethod
    def _normalize_location(cls, value: str) -> str:
        v = cls._normalize_token(value)
        return cls._LOCATION_ALIASES.get(v, v)

    @staticmethod
    def _normalize_token(value: str) -> str:
        return " ".join(value.strip().casefold().split())

