from __future__ import annotations

import json
from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from zomato_ai.phase1.dataset_loader import DatasetSpec, load_hf_dataset
from zomato_ai.phase1.preprocess import preprocess_to_artifact
from zomato_ai.phase1.schema import PreprocessConfig


def main() -> None:
    config = PreprocessConfig()
    ds = load_hf_dataset(DatasetSpec(name=config.dataset_name, split=config.dataset_split))

    # Convert to python dict rows for preprocessing.
    raw_rows = list(ds)
    result = preprocess_to_artifact(raw_rows, config, output_root=Path("data"))

    print(
        json.dumps(
            {
                "version": result.version,
                "restaurants_path": str(result.restaurants_path),
                "metadata_path": str(result.metadata_path),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

