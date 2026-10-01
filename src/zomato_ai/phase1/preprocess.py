from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import List, Optional, Tuple, Union

import pandas as pd

from zomato_ai.phase1.schema import CostBucket, PreprocessConfig


@dataclass(frozen=True)
class PreprocessResult:
    version: str
    restaurants_path: Path
    metadata_path: Path


def preprocess_to_artifact(
    raw_rows: list[dict[str, Any]],
    config: PreprocessConfig,
    output_root: Path,
) -> PreprocessResult:
    df_raw = pd.DataFrame(raw_rows)
    mapped = _map_to_canonical_columns(df_raw)
    df = _normalize_canonical_df(mapped)

    # Derive cost_bucket deterministically from cost numeric distribution.
    cost_series = pd.to_numeric(df["cost_numeric"], errors="coerce")
    q1, q2 = _cost_quantile_thresholds(cost_series, config.cost_bucket_quantiles)
    df["cost_bucket"] = df["cost_numeric"].apply(lambda x: _bucket_cost(x, q1, q2))

    # Final canonical columns
    out = pd.DataFrame(
        {
            "restaurant_id": df["restaurant_id"],
            "name": df["name"],
            "location": df["location"],
            "cuisine": df["cuisine"].apply(_cuisine_to_string),
            "dish_liked": df["dish_liked"].apply(_dish_liked_to_string),
            "rating": df["rating"],
            "cost_bucket": df["cost_bucket"],
            "cost_for_two": df["cost_for_two"],
        }
    )

    # Deterministic version id from: dataset config + mappings + thresholds.
    version = _compute_version(
        {
            "dataset_name": config.dataset_name,
            "dataset_split": config.dataset_split,
            "output_format": config.output_format,
            "cost_bucket_quantiles": list(config.cost_bucket_quantiles),
            "cost_bucket_thresholds": {"q1": q1, "q2": q2},
            "canonical_columns": list(out.columns),
        }
    )

    out_dir = output_root / "processed" / version
    out_dir.mkdir(parents=True, exist_ok=True)

    restaurants_path = _write_restaurants(out, out_dir, config.output_format)
    metadata_path = out_dir / "metadata.json"
    _write_metadata(
        metadata_path,
        {
            "version": version,
            "dataset": {"name": config.dataset_name, "split": config.dataset_split},
            "row_count": int(len(out)),
            "cost_bucket_thresholds": {"q1": q1, "q2": q2},
            "columns": list(out.columns),
            "notes": "Canonical contract: restaurant_id, name, location, cuisine, dish_liked, rating, cost_bucket, cost_for_two",
        },
    )

    return PreprocessResult(
        version=version, restaurants_path=restaurants_path, metadata_path=metadata_path
    )


def _map_to_canonical_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Map arbitrary dataset columns to the project's canonical fields.

    The source dataset schema can vary; we try common column names.
    """

    cols = {c.lower().strip(): c for c in df.columns}

    def pick(*candidates: str) -> Optional[str]:
        for c in candidates:
            if c in cols:
                return cols[c]
        return None

    name_col = pick(
        "name",
        "restaurant name",
        "restaurant_name",
        "restaurant",
        "restaurantname",
    )
    location_col = pick(
        "location",
        "city",
        "locality",
        "area",
        "address",
    )
    cuisine_col = pick(
        "cuisine",
        "cuisines",
        "cusine",
        "food_type",
        "food type",
    )
    dish_liked_col = pick(
        "dish_liked",
        "dish liked",
        "dishes_liked",
        "dishes liked",
        "dishliked",
    )
    rating_col = pick(
        "rating",
        "aggregate_rating",
        "aggregate rating",
        "rate",
        "user_rating",
        "user rating",
    )
    cost_col = pick(
        "average_cost_for_two",
        "average cost for two",
        "cost_for_two",
        "cost",
        "approx_cost(for two people)",
        "approx cost(for two people)",
        "approx_cost_for_two",
    )
    id_col = pick("restaurant_id", "id", "res_id", "res id", "restaurantid")

    if name_col is None:
        raise ValueError(
            f"Could not find a restaurant name column. Available columns: {list(df.columns)}"
        )

    out = pd.DataFrame()
    out["name"] = df[name_col]
    out["location_raw"] = df[location_col] if location_col else ""
    out["cuisine_raw"] = df[cuisine_col] if cuisine_col else ""
    out["dish_liked_raw"] = df[dish_liked_col] if dish_liked_col else ""
    out["rating_raw"] = df[rating_col] if rating_col else None
    out["cost_raw"] = df[cost_col] if cost_col else None
    out["source_id_raw"] = df[id_col] if id_col else None
    return out


def _normalize_canonical_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out["name"] = out["name"].astype(str).str.strip()
    out["location"] = out["location_raw"].astype(str).str.strip()
    out["location"] = out["location"].replace({"": "Unknown"})

    out["cuisine"] = out["cuisine_raw"].apply(_normalize_cuisine)
    out["dish_liked"] = out["dish_liked_raw"].apply(_normalize_dish_liked)

    out["rating"] = out["rating_raw"].apply(_normalize_rating)
    out["rating"] = out["rating"].fillna(0.0).clip(0.0, 5.0)

    out["cost_numeric"] = out["cost_raw"].apply(_normalize_cost_numeric)
    # Actual cost for two (INR), left missing when the source has no value.
    out["cost_for_two"] = out["cost_numeric"]
    out["cost_numeric"] = out["cost_numeric"].fillna(out["cost_numeric"].median())
    out["cost_numeric"] = out["cost_numeric"].fillna(0.0)

    out["restaurant_id"] = out.apply(_derive_restaurant_id, axis=1)
    return out


def _normalize_cuisine(val: Any) -> Union[str, List[str]]:
    if val is None:
        return "Unknown"
    if isinstance(val, list):
        cleaned = [str(x).strip() for x in val if str(x).strip()]
        return cleaned if cleaned else "Unknown"
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none"}:
        return "Unknown"
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts if parts else "Unknown"
    return s


def _cuisine_to_string(val: Any) -> str:
    if val is None:
        return "Unknown"
    if isinstance(val, list):
        cleaned = [str(x).strip() for x in val if str(x).strip()]
        return ", ".join(cleaned) if cleaned else "Unknown"
    s = str(val).strip()
    return s if s else "Unknown"


def _normalize_dish_liked(val: Any) -> Union[str, List[str]]:
    if val is None:
        return "Unknown"
    if isinstance(val, list):
        cleaned = [str(x).strip() for x in val if str(x).strip()]
        return cleaned if cleaned else "Unknown"
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none"}:
        return "Unknown"
    if "," in s:
        parts = [p.strip() for p in s.split(",") if p.strip()]
        return parts if parts else "Unknown"
    return s


def _dish_liked_to_string(val: Any) -> str:
    if val is None:
        return "Unknown"
    if isinstance(val, list):
        cleaned = [str(x).strip() for x in val if str(x).strip()]
        return ", ".join(cleaned) if cleaned else "Unknown"
    s = str(val).strip()
    return s if s else "Unknown"


def _normalize_rating(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    if "/" in s:
        s = s.split("/", 1)[0].strip()
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_cost_numeric(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in {"nan", "none"}:
        return None
    s = s.replace(",", "")
    s = "".join(ch for ch in s if (ch.isdigit() or ch == "." or ch == "-"))
    try:
        return float(s)
    except ValueError:
        return None


def _derive_restaurant_id(row: pd.Series) -> str:
    raw = row.get("source_id_raw", None)
    if raw is not None:
        s = str(raw).strip()
        if s and s.lower() not in {"nan", "none"}:
            return s

    payload = {
        "name": str(row.get("name", "")).strip(),
        "location": str(row.get("location", "")).strip(),
        "cuisine": row.get("cuisine", "Unknown"),
    }
    as_json = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(as_json.encode("utf-8")).hexdigest()[:16]


def _cost_quantile_thresholds(
    s: pd.Series, quantiles: Union[Tuple[float, float], List[float], Any]
) -> Tuple[float, float]:
    q = list(quantiles)
    if len(q) != 2:
        raise ValueError("cost_bucket_quantiles must contain exactly 2 values")
    q1 = float(s.quantile(q[0], interpolation="linear"))
    q2 = float(s.quantile(q[1], interpolation="linear"))
    if q2 < q1:
        q1, q2 = q2, q1
    return q1, q2


def _bucket_cost(x: Any, q1: float, q2: float) -> CostBucket:
    try:
        v = float(x)
    except Exception:
        v = q1
    if v <= q1:
        return "low"
    if v <= q2:
        return "medium"
    return "high"


def _compute_version(payload: dict[str, Any]) -> str:
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def _write_restaurants(df: pd.DataFrame, out_dir: Path, fmt: str) -> Path:
    if fmt == "parquet":
        path = out_dir / "restaurants.parquet"
        df.to_parquet(path, index=False)
        return path
    if fmt == "csv":
        path = out_dir / "restaurants.csv"
        df.to_csv(path, index=False)
        return path
    if fmt == "jsonl":
        path = out_dir / "restaurants.jsonl"
        df.to_json(path, orient="records", lines=True, force_ascii=False)
        return path
    raise ValueError(f"Unsupported output_format: {fmt}")


def _write_metadata(path: Path, obj: dict[str, Any]) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

