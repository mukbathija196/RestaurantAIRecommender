from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import PreferenceNormalizer, UserPreferences
from zomato_ai.phase2.selector import DeterministicCandidateSelector


class TestPhase2Selector(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.artifact = Path(self.tempdir.name) / "restaurants.parquet"
        df = pd.DataFrame(
            [
                {
                    "restaurant_id": "r1",
                    "name": "A",
                    "location": "BTM",
                    "cuisine": "Italian, Pizza",
                    "rating": 4.8,
                    "cost_bucket": "high",
                },
                {
                    "restaurant_id": "r2",
                    "name": "B",
                    "location": "BTM",
                    "cuisine": "Italian",
                    "rating": 4.4,
                    "cost_bucket": "medium",
                },
                {
                    "restaurant_id": "r3",
                    "name": "C",
                    "location": "HSR",
                    "cuisine": "Chinese",
                    "rating": 4.7,
                    "cost_bucket": "medium",
                },
                {
                    "restaurant_id": "r4",
                    "name": "D",
                    "location": "BTM",
                    "cuisine": "Chinese",
                    "rating": 3.9,
                    "cost_bucket": "medium",
                },
                # duplicate id to ensure dedupe path is stable
                {
                    "restaurant_id": "r2",
                    "name": "B",
                    "location": "BTM",
                    "cuisine": "Italian",
                    "rating": 4.4,
                    "cost_bucket": "medium",
                },
            ]
        )
        df.to_parquet(self.artifact, index=False)

        self.catalog = RestaurantCatalog(self.artifact)
        self.selector = DeterministicCandidateSelector(self.catalog)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_budget_mapping(self) -> None:
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        norm = PreferenceNormalizer.normalize(prefs)
        self.assertEqual(norm.allowed_cost_buckets, ["medium"])

    def test_cuisine_normalization(self) -> None:
        prefs = UserPreferences(
            location="  BTM ",
            budget="medium",
            cuisines=["  ITALIAN  ", "  Chinese "],
            min_rating=4.0,
            extra_preferences=[],
        )
        norm = PreferenceNormalizer.normalize(prefs)
        self.assertEqual(norm.location_norm, "btm")
        self.assertEqual(norm.cuisines_norm, ["italian", "chinese"])

    def test_constraints_are_respected(self) -> None:
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        norm = PreferenceNormalizer.normalize(prefs, location_match_mode="exact")
        result = self.selector.select(norm, top_k=10)

        self.assertGreaterEqual(result.total_after_filters, 1)
        self.assertEqual(len(result.candidates), 1)

        row = result.candidates.iloc[0]
        self.assertEqual(row["restaurant_id"], "r2")
        self.assertEqual(row["location"], "BTM")
        self.assertGreaterEqual(float(row["rating"]), 4.0)
        self.assertEqual(row["cost_bucket"], "medium")
        self.assertIn("italian", str(row["cuisine"]).casefold())

    def test_deterministic_top_k(self) -> None:
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        norm = PreferenceNormalizer.normalize(prefs, location_match_mode="exact")
        first = self.selector.select(norm, top_k=10).candidates["restaurant_id"].tolist()
        second = self.selector.select(norm, top_k=10).candidates["restaurant_id"].tolist()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

