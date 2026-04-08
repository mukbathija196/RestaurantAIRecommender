from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_processed_artifact_path(explicit: Optional[str] = None) -> str:
    """
    Resolve path to processed restaurants artifact (parquet/csv/jsonl).

    Order:
    1. explicit argument
    2. env `DATA_ARTIFACT_PATH`
    3. latest version folder under `data/processed/`
    """
    if explicit:
        return explicit

    env_path = os.getenv("DATA_ARTIFACT_PATH", "").strip()
    if env_path:
        return env_path

    processed = Path("data/processed")
    if not processed.exists():
        raise FileNotFoundError(
            "No processed dataset found. Set DATA_ARTIFACT_PATH or run scripts/preprocess_restaurants.py."
        )
    versions = [p for p in processed.iterdir() if p.is_dir()]
    if not versions:
        raise FileNotFoundError(
            "No processed dataset found. Set DATA_ARTIFACT_PATH or run scripts/preprocess_restaurants.py."
        )
    latest = max(versions, key=lambda p: p.stat().st_mtime)
    for name in ("restaurants.parquet", "restaurants.csv", "restaurants.jsonl"):
        p = latest / name
        if p.exists():
            return str(p)
    raise FileNotFoundError(f"No restaurants artifact in {latest}")
