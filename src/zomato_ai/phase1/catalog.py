from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class CatalogStats:
    row_count: int
    distinct_locations: int


class RestaurantCatalog:
    """
    Loads the Phase 1 processed artifact and provides query primitives.
    """

    def __init__(self, restaurants_path: Path):
        self._path = restaurants_path
        self._df = _load_artifact(restaurants_path)

        # Normalized columns for query performance
        self._df["_location_norm"] = self._df["location"].astype(str).str.strip().str.casefold()

    @property
    def stats(self) -> CatalogStats:
        return CatalogStats(
            row_count=int(len(self._df)),
            distinct_locations=int(self._df["_location_norm"].nunique()),
        )

    def query(
        self,
        *,
        location: Optional[str] = None,
        location_match: str = "contains",
        min_rating: Optional[float] = None,
        limit: int = 20,
    ) -> pd.DataFrame:
        df = self._df

        if location:
            loc = str(location).strip().casefold()
            if location_match == "exact":
                df = df[df["_location_norm"] == loc]
            elif location_match == "contains":
                df = df[df["_location_norm"].str.contains(loc, na=False)]
            else:
                raise ValueError("location_match must be one of: 'exact', 'contains'")

        if min_rating is not None:
            df = df[pd.to_numeric(df["rating"], errors="coerce").fillna(0.0) >= float(min_rating)]

        df = df.sort_values(by=["rating"], ascending=False)
        return df.head(int(limit)).drop(columns=["_location_norm"])

    def to_dataframe(self) -> pd.DataFrame:
        # Return a copy so callers cannot mutate internal state.
        return self._df.copy()


def _load_artifact(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Processed artifact not found at: {path}")

    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix == ".jsonl":
        return pd.read_json(path, lines=True)

    raise ValueError(f"Unsupported artifact format: {suffix}")

