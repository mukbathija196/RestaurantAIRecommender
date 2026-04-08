from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _bootstrap_workspace_hf_cache() -> None:
    """
    Set HF cache env vars as early as possible (module import time).

    Some HF libraries read these env vars on import and cache the derived paths.
    """

    cwd = Path.cwd()
    os.environ.setdefault("XDG_CACHE_HOME", str(cwd / ".cache"))
    os.environ.setdefault("HF_HOME", str(cwd / ".hf_home"))
    os.environ.setdefault("HF_DATASETS_CACHE", str(cwd / ".hf_datasets_cache"))
    os.environ.setdefault("HUGGINGFACE_HUB_CACHE", str(cwd / ".hf_hub_cache"))
    os.environ.setdefault("HF_HUB_CACHE", str(cwd / ".hf_hub_cache"))


_bootstrap_workspace_hf_cache()

from datasets import Dataset, load_dataset  # noqa: E402


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    split: str = "train"


def load_hf_dataset(spec: DatasetSpec) -> Dataset:
    """
    Loads a Hugging Face dataset split.

    Note: `datasets` handles its own caching under the hood.
    """

    return load_dataset(spec.name, split=spec.split)


def snapshot_dataset_to_jsonl(ds: Dataset, output_path: Path) -> Path:
    """
    Optional raw snapshot for repeatability.
    Writes a JSONL file of the raw dataset rows.
    """

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in ds:
            f.write(_to_json_line(row))
            f.write("\n")
    return output_path


def _to_json_line(row: dict[str, Any]) -> str:
    import json

    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

