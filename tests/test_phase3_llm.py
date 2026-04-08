from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

import pandas as pd
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import PreferenceNormalizer, UserPreferences
from zomato_ai.phase3.llm_output_parser import parse_json_object
from zomato_ai.phase3.llm_output_validator import validate_llm_payload
from zomato_ai.phase3.orchestrator import RecommendationOrchestrator
from zomato_ai.phase3.prompt_builder import PromptBuilder


class TestPhase3Parser(unittest.TestCase):
    def test_parse_plain_json(self) -> None:
        text = '{"recommendations": [{"rank": 1, "restaurant_id": "a", "explanation": "x"}]}'
        obj = parse_json_object(text)
        self.assertEqual(obj["recommendations"][0]["restaurant_id"], "a")

    def test_parse_markdown_fence(self) -> None:
        text = '```json\n{"recommendations": [{"rank": 1, "restaurant_id": "b", "explanation": "y"}]}\n```'
        obj = parse_json_object(text)
        self.assertEqual(obj["recommendations"][0]["restaurant_id"], "b")

    def test_parse_json_embedded_in_prose(self) -> None:
        text = (
            "Here is the result:\n"
            '{"recommendations": [{"rank": 1, "restaurant_id": "c", "explanation": "z"}]}\n'
            "Hope this helps."
        )
        obj = parse_json_object(text)
        self.assertEqual(obj["recommendations"][0]["restaurant_id"], "c")


class TestPhase3Validator(unittest.TestCase):
    def test_valid(self) -> None:
        data = {
            "recommendations": [
                {"rank": 1, "restaurant_id": "r1", "explanation": "Because Italian and rating."},
            ]
        }
        payload, _ = validate_llm_payload(
            data,
            allowed_ids={"r1"},
            max_rank=1,
        )
        self.assertEqual(len(payload.recommendations), 1)


class TestPhase3Orchestrator(unittest.TestCase):
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
                {
                    "restaurant_id": "r2",
                    "name": "Noodles",
                    "location": "BTM",
                    "cuisine": "Chinese",
                    "dish_liked": "Chilli garlic noodles",
                    "rating": 4.2,
                    "cost_bucket": "medium",
                },
                {
                    "restaurant_id": "r3",
                    "name": "Pasta Place",
                    "location": "BTM",
                    "cuisine": "Italian",
                    "dish_liked": "Alfredo pasta",
                    "rating": 4.4,
                    "cost_bucket": "medium",
                },
            ]
        )
        df.to_parquet(self.artifact, index=False)
        self.catalog = RestaurantCatalog(self.artifact)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_orchestrator_with_mock_llm(self) -> None:
        def fake_gen(_prompt: str) -> str:
            return (
                '{"recommendations": ['
                '{"rank": 1, "restaurant_id": "r1", "explanation": "Strong Italian match and rating."}'
                "]}"
            )

        orch = RecommendationOrchestrator(self.catalog, generate_fn=fake_gen)
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        result = orch.recommend(prefs, location_match_mode="exact", result_limit=5)
        self.assertFalse(result.used_fallback)
        self.assertEqual(len(result.recommendations), 1)
        self.assertEqual(result.recommendations[0]["restaurant_id"], "r1")
        self.assertIn("explanation", result.recommendations[0])

    def test_fallback_on_bad_json(self) -> None:
        def bad_gen(_prompt: str) -> str:
            return "not json at all"

        orch = RecommendationOrchestrator(self.catalog, generate_fn=bad_gen)
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=[],
            min_rating=4.0,
            extra_preferences=[],
        )
        result = orch.recommend(prefs, location_match_mode="exact", result_limit=2)
        self.assertTrue(result.used_fallback)
        self.assertGreaterEqual(len(result.recommendations), 1)

    def test_dedup_same_name_in_single_result_set(self) -> None:
        def fake_gen(_prompt: str) -> str:
            return (
                '{"recommendations": ['
                '{"rank": 1, "restaurant_id": "r1", "explanation": "Great fit."},'
                '{"rank": 2, "restaurant_id": "r3", "explanation": "Also great fit."}'
                "]}"
            )

        orch = RecommendationOrchestrator(self.catalog, generate_fn=fake_gen)
        prefs = UserPreferences(
            location="BTM",
            budget="medium",
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        result = orch.recommend(prefs, location_match_mode="exact", result_limit=5)
        names = [str(r.get("name", "")) for r in result.recommendations]
        self.assertEqual(names.count("Pasta Place"), 1)


class TestPhase3PromptBuilder(unittest.TestCase):
    def test_any_constraints_not_in_prompt_payload(self) -> None:
        prefs = UserPreferences(
            location="",
            budget="medium",
            allowed_cost_buckets=[],
            cuisines=["Italian"],
            min_rating=4.0,
            extra_preferences=[],
        )
        normalized = PreferenceNormalizer.normalize(prefs, location_match_mode="contains")
        candidates = pd.DataFrame(
            [
                {
                    "restaurant_id": "r1",
                    "name": "Pasta Place",
                    "location": "BTM",
                    "cuisine": "Italian",
                    "dish_liked": "Truffle pasta",
                    "rating": 4.5,
                    "cost_bucket": "medium",
                }
            ]
        )
        prompt = PromptBuilder().build_ranking_prompt(normalized, candidates)
        payload = json.loads(prompt.split("Input JSON:\n", 1)[1])
        up = payload["user_preferences"]
        self.assertNotIn("location", up)
        self.assertNotIn("budget", up)


if __name__ == "__main__":
    unittest.main()
