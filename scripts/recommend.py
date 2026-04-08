from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import UserPreferences
from zomato_ai.phase3.env_config import load_env_from_dotenv, require_gemini_api_key
from zomato_ai.phase3.orchestrator import RecommendationOrchestrator


def _resolve_artifact_path(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    processed = Path("data/processed")
    if not processed.exists():
        raise FileNotFoundError("No processed data. Run scripts/preprocess_restaurants.py first.")
    versions = [p for p in processed.iterdir() if p.is_dir()]
    if not versions:
        raise FileNotFoundError("No processed data. Run scripts/preprocess_restaurants.py first.")
    latest = max(versions, key=lambda p: p.stat().st_mtime)
    for name in ("restaurants.parquet", "restaurants.csv", "restaurants.jsonl"):
        p = latest / name
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"No restaurants artifact in {latest}")


def main() -> None:
    p = argparse.ArgumentParser(description="Phase 3: Gemini recommendations (orchestrator).")
    p.add_argument("--artifact", default=None)
    p.add_argument("--location", required=True)
    p.add_argument("--budget", required=True, choices=["low", "medium", "high"])
    p.add_argument("--cuisine", action="append", default=[])
    p.add_argument("--min-rating", type=float, default=0.0)
    p.add_argument("--extra-pref", action="append", default=[])
    p.add_argument("--location-match", default="contains", choices=["contains", "exact"])
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--dry-run", action="store_true", help="Skip Gemini; use deterministic fallback only.")
    args = p.parse_args()

    load_env_from_dotenv()
    if not args.dry_run:
        require_gemini_api_key()

    artifact = _resolve_artifact_path(args.artifact)
    catalog = RestaurantCatalog(Path(artifact))
    prefs = UserPreferences(
        location=args.location,
        budget=args.budget,
        cuisines=args.cuisine,
        min_rating=args.min_rating,
        extra_preferences=args.extra_pref,
    )

    if args.dry_run:

        def _dry(_prompt: str) -> str:
            raise RuntimeError("dry-run forces fallback")

        orch = RecommendationOrchestrator(catalog, generate_fn=_dry)
    else:
        orch = RecommendationOrchestrator(catalog)

    result = orch.recommend(
        prefs,
        location_match_mode=args.location_match,
        result_limit=args.limit,
    )
    print(
        json.dumps(
            {
                "used_fallback": result.used_fallback,
                "llm_model": result.llm_model,
                "prompt_version": result.prompt_version,
                "candidate_count": result.candidate_count,
                "total_after_filters": result.total_after_filters,
                "error": result.error,
                "recommendations": result.recommendations,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
