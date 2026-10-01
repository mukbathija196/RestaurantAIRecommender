from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_env_from_dotenv() -> None:
    """Load `.env` from project root (cwd) if present."""
    load_dotenv(Path.cwd() / ".env", override=False)


def get_gemini_api_key() -> Optional[str]:
    return os.getenv("GEMINI_API_KEY", "").strip() or None


def require_gemini_api_key() -> str:
    load_env_from_dotenv()
    key = get_gemini_api_key()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Add it to a `.env` file in the project root "
            "(see `.env.example`)."
        )
    return key


DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def get_gemini_model_name() -> str:
    return os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip() or DEFAULT_GEMINI_MODEL
