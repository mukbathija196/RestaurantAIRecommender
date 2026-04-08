from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fastapi.testclient import TestClient

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase3.orchestrator import RecommendationOrchestrator
from zomato_ai.phase4.app import create_app


class TestPhase4Api(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.artifact = Path(self.tempdir.name) / "restaurants.parquet"
        df = pd.DataFrame(
            [
                {
                    "restaurant_id": "r1",
                    "name": "Pasta Place",
                    "location": "BTM",
                    "cuisine": "Italian",
                    "dish_liked": "Truffle pasta",
                    "rating": 4.5,
                    "cost_bucket": "medium",
                },
            ]
        )
        df.to_parquet(self.artifact, index=False)
        self.catalog = RestaurantCatalog(self.artifact)

        def fake_gen(_prompt: str) -> str:
            return (
                '{"recommendations": ['
                '{"rank": 1, "restaurant_id": "r1", "explanation": "Italian match in BTM."}'
                "]}"
            )

        self.orch = RecommendationOrchestrator(self.catalog, generate_fn=fake_gen)
        self._test_client = TestClient(create_app(injected_orchestrator=self.orch))
        self._test_client.__enter__()

    def tearDown(self) -> None:
        self._test_client.__exit__(None, None, None)
        self.tempdir.cleanup()

    def test_post_recommendations(self) -> None:
        res = self._test_client.post(
            "/recommendations",
            json={
                "city": "Bengaluru",
                "locality": "BTM",
                "budget_min": 500,
                "budget_max": 1500,
                "cuisines": ["Italian"],
                "min_rating": 4.0,
                "extra_preferences": [],
                "location_match": "exact",
                "limit": 5,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("request_id", data)
        self.assertEqual(len(data["recommendations"]), 1)
        self.assertEqual(data["recommendations"][0]["restaurant_id"], "r1")
        self.assertEqual(data["recommendations"][0]["dish_liked"], "Truffle pasta")
        self.assertIn("meta", data)
        self.assertEqual(data["meta"]["prompt_version"], "3")

    def test_validation_error(self) -> None:
        res = self._test_client.post(
            "/recommendations",
            json={"location": "", "budget_min": 300, "budget_max": 900, "min_rating": 5.5},
        )
        self.assertEqual(res.status_code, 422)

    def test_ui_html_served(self) -> None:
        res = self._test_client.get("/ui/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Restaurant recommendations", res.content)

    def test_ui_options_served(self) -> None:
        res = self._test_client.get("/ui/options")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("cities", data)
        self.assertIn("localities_by_city", data)
        self.assertIn("cuisines", data)
        self.assertIn("popular_cuisines", data)
        self.assertIn("0-1000", data["budget_bands"])

    def test_any_locality_any_budget(self) -> None:
        res = self._test_client.post(
            "/recommendations",
            json={
                "city": "Bengaluru",
                "locality": "",
                "cuisines": ["Italian"],
                "min_rating": 4.0,
                "extra_preferences": [],
                "location_match": "contains",
                "limit": 5,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(len(data["recommendations"]), 1)


if __name__ == "__main__":
    unittest.main()
