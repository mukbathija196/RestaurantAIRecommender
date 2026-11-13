"""Vercel serverless entrypoint for the FastAPI backend."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)  # data/processed/ and .env are resolved relative to cwd

# Pin the dataset version: directory mtimes are not preserved on deploy.
os.environ.setdefault(
    "DATA_ARTIFACT_PATH",
    str(ROOT / "data" / "processed" / "57175fee349f" / "restaurants.parquet"),
)

from zomato_ai.phase4.app import app  # noqa: E402,F401
