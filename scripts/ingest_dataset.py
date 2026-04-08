from __future__ import annotations

from pathlib import Path

import sys

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from zomato_ai.phase1.dataset_loader import DatasetSpec, load_hf_dataset, snapshot_dataset_to_jsonl


def main() -> None:
    spec = DatasetSpec(name="ManikaSaini/zomato-restaurant-recommendation", split="train")
    ds = load_hf_dataset(spec)

    out_path = Path("data/raw") / "zomato_restaurants_train.jsonl"
    snapshot_dataset_to_jsonl(ds, out_path)
    print(f"Wrote raw snapshot: {out_path} (rows={len(ds)})")


if __name__ == "__main__":
    main()

