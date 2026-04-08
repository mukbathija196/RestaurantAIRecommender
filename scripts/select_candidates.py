from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import PreferenceNormalizer, UserPreferences
from zomato_ai.phase2.selector import DeterministicCandidateSelector


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 2 deterministic candidate selection.")
    p.add_argument("--artifact", default=None, help="Path to processed restaurants artifact.")
    p.add_argument("--location", required=True)
    p.add_argument("--budget", required=True, choices=["low", "medium", "high"])
    p.add_argument("--cuisine", action="append", default=[], help="Repeatable cuisine preference.")
    p.add_argument("--min-rating", type=float, default=0.0)
    p.add_argument("--extra-pref", action="append", default=[], help="Optional extra preferences.")
    p.add_argument("--location-match", default="contains", choices=["contains", "exact"])
    p.add_argument("--top-k", type=int, default=10)
    args = p.parse_args()

    artifact = _resolve_artifact_path(args.artifact)
    catalog = RestaurantCatalog(Path(artifact))
    selector = DeterministicCandidateSelector(catalog)

    prefs = UserPreferences(
        location=args.location,
        budget=args.budget,
        cuisines=args.cuisine,
        min_rating=args.min_rating,
        extra_preferences=args.extra_pref,
    )
    normalized = PreferenceNormalizer.normalize(prefs, location_match_mode=args.location_match)

    result = selector.select(normalized, top_k=args.top_k)
    print(
        json.dumps(
            {
                "artifact": artifact,
                "normalized_preferences": normalized.model_dump(),
                "total_after_filters": result.total_after_filters,
                "returned": int(len(result.candidates)),
            },
            indent=2,
        )
    )
    print(result.candidates.to_string(index=False))


def _resolve_artifact_path(explicit):
    if explicit:
        return explicit

    processed = Path("data/processed")
    if not processed.exists():
        raise FileNotFoundError("No processed artifacts found. Run scripts/preprocess_restaurants.py first.")

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

