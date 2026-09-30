from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase1.preprocess import preprocess_to_artifact
from zomato_ai.phase1.schema import PreprocessConfig
from zomato_ai.phase2.preferences import PreferenceNormalizer, UserPreferences
from zomato_ai.phase2.selector import DeterministicCandidateSelector
from zomato_ai.phase3.orchestrator import RecommendationOrchestrator
from zomato_ai.phase4.app import BUDGET_BANDS, create_app

# One restaurant per budget band, plus one with unknown cost.
COSTS = {
    "cheap": 200.0,
    "casual": 450.0,
    "mid": 800.0,
    "upscale": 1500.0,
    "fine": 3500.0,
    "unknown": None,
}


def _catalog_df() -> pd.DataFrame:
    rows = []
    for name, cost in COSTS.items():
        rows.append(
            {
                "restaurant_id": name,
                "name": name,
                "location": "Koramangala",
                "cuisine": "North Indian",
                "dish_liked": "Dal",
                "rating": 4.2,
                "cost_bucket": "low" if (cost or 0) <= 300 else ("medium" if cost <= 550 else "high"),
                "cost_for_two": cost,
            }
        )
    return pd.DataFrame(rows)


class _CatalogCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.artifact = Path(self.tempdir.name) / "restaurants.parquet"
        _catalog_df().to_parquet(self.artifact, index=False)
        self.catalog = RestaurantCatalog(self.artifact)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _select(self, **kwargs) -> pd.DataFrame:
        prefs = PreferenceNormalizer.normalize(
            UserPreferences(location="Koramangala", budget="medium", **kwargs)
        )
        return DeterministicCandidateSelector(self.catalog).select(prefs, top_k=10).candidates


class TestBudgetRangeFilter(_CatalogCase):
    def test_each_band_returns_different_restaurants(self) -> None:
        seen = {}
        for label, band in BUDGET_BANDS.items():
            names = tuple(self._select(budget_min=band["min"], budget_max=band["max"])["name"])
            seen[label] = names
        self.assertEqual(
            seen,
            {
                "Under ₹300": ("cheap",),
                "₹300 – ₹600": ("casual",),
                "₹600 – ₹1,000": ("mid",),
                "₹1,000 – ₹2,000": ("upscale",),
                "Over ₹2,000": ("fine",),
            },
        )

    def test_range_bounds_are_inclusive(self) -> None:
        names = set(self._select(budget_min=450, budget_max=800)["name"])
        self.assertEqual(names, {"casual", "mid"})

    def test_no_budget_keeps_unknown_cost(self) -> None:
        names = set(self._select(allowed_cost_buckets=[])["name"])
        self.assertEqual(names, set(COSTS))

    def test_reversed_range_is_swapped(self) -> None:
        names = set(self._select(budget_min=1000, budget_max=300)["name"])
        self.assertEqual(names, {"casual", "mid"})

    def test_budget_score_prefers_middle_of_range(self) -> None:
        # Same rating and cuisine, so only the budget score separates them.
        # Range 0-900 centres on 450: casual (450) > cheap (200) > mid (800).
        names = list(self._select(budget_min=0, budget_max=900)["name"])
        self.assertEqual(names, ["casual", "cheap", "mid"])

    def test_legacy_catalog_without_cost_falls_back_to_buckets(self) -> None:
        _catalog_df().drop(columns=["cost_for_two"]).to_parquet(self.artifact, index=False)
        self.catalog = RestaurantCatalog(self.artifact)
        names = set(
            self._select(budget_min=1001, budget_max=2000, allowed_cost_buckets=["high"])["name"]
        )
        self.assertEqual(names, {"mid", "upscale", "fine"})

    def test_legacy_bucket_score_prefers_requested_bucket(self) -> None:
        _catalog_df().drop(columns=["cost_for_two"]).to_parquet(self.artifact, index=False)
        self.catalog = RestaurantCatalog(self.artifact)
        names = list(self._select(allowed_cost_buckets=["low", "medium", "high"])["name"])
        # budget="medium": the medium-bucket restaurant ranks first; low and high tie behind it.
        self.assertEqual(names[0], "casual")


class TestBudgetApi(_CatalogCase):
    def setUp(self) -> None:
        super().setUp()
        self.prompts = []

        def fake_gen(prompt: str) -> str:
            self.prompts.append(prompt)
            payload = json.loads(prompt.split("Input JSON:\n", 1)[1])
            recs = [
                {"rank": i, "restaurant_id": c["restaurant_id"], "explanation": "Fits."}
                for i, c in enumerate(payload["candidates"], start=1)
            ]
            return json.dumps({"recommendations": recs})

        orch = RecommendationOrchestrator(self.catalog, generate_fn=fake_gen)
        self.client = TestClient(create_app(injected_orchestrator=orch))
        self.client.__enter__()

    def tearDown(self) -> None:
        self.client.__exit__(None, None, None)
        super().tearDown()

    def _post(self, band: dict) -> dict:
        res = self.client.post(
            "/recommendations",
            json={
                "locality": "Koramangala",
                "budget_min": band["min"],
                "budget_max": band["max"],
                "cuisines": ["North Indian"],
            },
        )
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()

    def test_bands_from_ui_options_give_different_results(self) -> None:
        bands = self.client.get("/ui/options").json()["budget_bands"]
        results = {k: tuple(r["name"] for r in self._post(b)["recommendations"]) for k, b in bands.items()}
        self.assertEqual(len(set(results.values())), len(bands), results)

    def test_prompt_carries_actual_range_and_costs(self) -> None:
        data = self._post({"min": 0.0, "max": 300.0})
        payload = json.loads(self.prompts[-1].split("Input JSON:\n", 1)[1])
        prefs = payload["user_preferences"]
        self.assertEqual(prefs["budget_for_two_inr"], {"min": 0.0, "max": 300.0})
        self.assertNotIn("budget", prefs)
        self.assertEqual(payload["candidates"][0]["cost_for_two"], 200.0)
        self.assertEqual(data["recommendations"][0]["estimated_cost"], "₹200 for two")


class TestPreprocessKeepsCost(unittest.TestCase):
    def test_cost_for_two_in_artifact(self) -> None:
        raw = [
            {"name": "A", "location": "BTM", "cuisines": "Cafe", "rate": "4.1/5", "approx_cost(for two people)": "1,200"},
            {"name": "B", "location": "BTM", "cuisines": "Cafe", "rate": "3.9/5", "approx_cost(for two people)": None},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            res = preprocess_to_artifact(raw, PreprocessConfig(), Path(tmp))
            df = pd.read_parquet(res.restaurants_path)
        costs = dict(zip(df["name"], df["cost_for_two"]))
        self.assertEqual(costs["A"], 1200.0)
        self.assertTrue(pd.isna(costs["B"]))


if __name__ == "__main__":
    unittest.main()
