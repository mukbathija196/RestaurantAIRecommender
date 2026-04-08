from __future__ import annotations

from dataclasses import dataclass
from typing import List

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
        df["_score_budget"] = 1.0

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

