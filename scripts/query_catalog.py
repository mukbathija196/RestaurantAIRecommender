from __future__ import annotations

import argparse
import json
from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from zomato_ai.phase1.catalog import RestaurantCatalog


def main() -> None:
    p = argparse.ArgumentParser(description="Query the processed restaurant catalog.")
    p.add_argument("--artifact", default=None, help="Path to processed restaurants artifact.")
    p.add_argument("--location", default=None, help="Exact location match (case-insensitive).")
    p.add_argument(
        "--location-match",
        default="contains",
        choices=["contains", "exact"],
        help="Location matching mode (default: contains).",
    )
    p.add_argument("--min-rating", type=float, default=None, help="Minimum rating threshold.")
    p.add_argument("--limit", type=int, default=10, help="Number of rows to return.")
    args = p.parse_args()

    artifact = _resolve_artifact_path(args.artifact)
    cat = RestaurantCatalog(Path(artifact))

    df = cat.query(
        location=args.location,
        location_match=args.location_match,
        min_rating=args.min_rating,
        limit=args.limit,
    )
    print(json.dumps({"artifact": artifact, "stats": cat.stats.__dict__}, indent=2))
    print(df.to_string(index=False))


def _resolve_artifact_path(explicit):
    if explicit:
        return explicit

    processed = Path("data/processed")
    if not processed.exists():
        raise FileNotFoundError("No processed artifacts found. Run scripts/preprocess_restaurants.py first.")

    # Pick most recently modified artifact among version folders.
    versions = [p for p in processed.iterdir() if p.is_dir()]
    if not versions:
        raise FileNotFoundError("No processed artifacts found. Run scripts/preprocess_restaurants.py first.")

    latest = max(versions, key=lambda p: p.stat().st_mtime)
    for candidate in ["restaurants.parquet", "restaurants.csv", "restaurants.jsonl"]:
        path = latest / candidate
        if path.exists():
            return str(path)

    raise FileNotFoundError(f"No restaurants artifact found in: {latest}")


if __name__ == "__main__":
    main()

