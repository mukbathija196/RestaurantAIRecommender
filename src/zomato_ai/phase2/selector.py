from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import pandas as pd

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import UserPreferencesNormalized


@dataclass(frozen=True)
class CandidateSelectionResult:
    candidates: pd.DataFrame
    total_after_filters: int


class DeterministicCandidateSelector:
    """
    Applies hard filters and deterministic scoring to select top K candidates.
    """

    def __init__(self, catalog: RestaurantCatalog):
        self._catalog = catalog

    def select(
        self,
        prefs: UserPreferencesNormalized,
        *,
        top_k: int = 20,
    ) -> CandidateSelectionResult:
        df = self._catalog.to_dataframe()

        df["_location_norm"] = df["location"].astype(str).str.strip().str.casefold()
        df["_cuisine_norm"] = df["cuisine"].astype(str).str.casefold()
        df["_rating_num"] = pd.to_numeric(df["rating"], errors="coerce").fillna(0.0)

        if prefs.location_norm:
            if prefs.location_match_mode == "exact":
                df = df[df["_location_norm"] == prefs.location_norm]
            else:
                df = df[df["_location_norm"].str.contains(prefs.location_norm, na=False)]

        df = df[df["_rating_num"] >= prefs.min_rating]

        use_cost_range = _has_budget_range(prefs) and "cost_for_two" in df.columns
        if use_cost_range:
            df["_cost_num"] = pd.to_numeric(df["cost_for_two"], errors="coerce")
            lo = prefs.budget_min if prefs.budget_min is not None else 0.0
            hi = prefs.budget_max if prefs.budget_max is not None else float("inf")
            df = df[df["_cost_num"].between(lo, hi)]
        else:
            allowed = set(prefs.allowed_cost_buckets)
            if allowed:
                df = df[df["cost_bucket"].isin(allowed)]

        if prefs.cuisines_norm:
            cuisine_mask = df["_cuisine_norm"].apply(
                lambda s: any(c in s for c in prefs.cuisines_norm)
            )
            df = df[cuisine_mask]

        filtered_count = int(len(df))
        if filtered_count == 0:
            return CandidateSelectionResult(candidates=df.drop(columns=self._meta_cols(df)), total_after_filters=0)

        df["_score_rating"] = df["_rating_num"] / 5.0
        df["_score_cuisine"] = df["_cuisine_norm"].apply(
            lambda s: _cuisine_score(s, prefs.cuisines_norm)
        )
        if use_cost_range:
            df["_score_budget"] = df["_cost_num"].apply(
                lambda c: _budget_range_score(c, prefs.budget_min, prefs.budget_max)
            )
        else:
            df["_score_budget"] = df["cost_bucket"].apply(
                lambda b: _budget_bucket_score(b, prefs)
            )

        df["_score_total"] = (
            0.6 * df["_score_rating"] + 0.3 * df["_score_cuisine"] + 0.1 * df["_score_budget"]
        )

        df = df.sort_values(
            by=["_score_total", "_rating_num", "name", "restaurant_id"],
            ascending=[False, False, True, True],
            kind="mergesort",
        )

        df = df.drop_duplicates(subset=["restaurant_id"], keep="first")
        selected = df.head(int(top_k)).drop(columns=self._meta_cols(df))

        return CandidateSelectionResult(
            candidates=selected.reset_index(drop=True),
            total_after_filters=filtered_count,
        )

    @staticmethod
    def _meta_cols(df: pd.DataFrame) -> List[str]:
        return [c for c in df.columns if c.startswith("_")]


def _cuisine_score(cuisine_norm: str, wanted: List[str]) -> float:
    if not wanted:
        return 0.5
    if not cuisine_norm:
        return 0.0

    exact_hits = sum(1 for c in wanted if c == cuisine_norm)
    contains_hits = sum(1 for c in wanted if c in cuisine_norm)

    raw = (2 * exact_hits) + contains_hits
    max_raw = max(1, 2 * len(wanted))
    score = raw / float(max_raw)
    if score > 1.0:
        return 1.0
    return score



def _has_budget_range(prefs: UserPreferencesNormalized) -> bool:
    return prefs.budget_min is not None or prefs.budget_max is not None


_BUCKET_ORDER = {"low": 0, "medium": 1, "high": 2}


def _budget_range_score(cost: float, lo: Optional[float], hi: Optional[float]) -> float:
    """
    1.0 at the middle of the requested range, easing to 0.5 at its edges.

    Open-ended ranges ("under X" / "X and up") have no middle, so every
    in-range restaurant scores 1.0.
    """
    if lo is None or hi is None or hi <= lo:
        return 1.0
    mid = (lo + hi) / 2.0
    half = (hi - lo) / 2.0
    dist = min(1.0, abs(float(cost) - mid) / half)
    return 1.0 - 0.5 * dist


def _budget_bucket_score(bucket: str, prefs: UserPreferencesNormalized) -> float:
    """
    Legacy path for catalogs without `cost_for_two`: exact bucket match 1.0,
    one bucket away 0.5, further 0.0. No budget preference is neutral (1.0).
    """
    if not prefs.allowed_cost_buckets:
        return 1.0
    want = _BUCKET_ORDER.get(prefs.budget)
    got = _BUCKET_ORDER.get(str(bucket))
    if want is None or got is None:
        return 0.5
    return {0: 1.0, 1: 0.5}.get(abs(want - got), 0.0)
