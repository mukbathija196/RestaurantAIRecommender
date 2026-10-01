from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zomato_ai.phase3.gemini_client import GeminiGenerationConfig, GeminiLlmClient


class _FakeModels:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        result = self._responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _client(*responses):
    models = _FakeModels(responses)
    return GeminiLlmClient(
        model_name="test-model",
        system_instruction="Return JSON only.",
        client=SimpleNamespace(models=models),
    ), models


class TestGeminiLlmClient(unittest.TestCase):
    def test_passes_model_system_instruction_and_json_mode(self) -> None:
        llm, models = _client(SimpleNamespace(text='{"ok": true}', candidates=[]))
        out = llm.generate_text("hi", GeminiGenerationConfig(temperature=0.0, max_output_tokens=10))
        self.assertEqual(out, '{"ok": true}')
        call = models.calls[0]
        self.assertEqual(call["model"], "test-model")
        self.assertEqual(call["contents"], "hi")
        self.assertEqual(call["config"].system_instruction, "Return JSON only.")
        self.assertEqual(call["config"].response_mime_type, "application/json")
        self.assertEqual(call["config"].temperature, 0.0)
        self.assertEqual(call["config"].max_output_tokens, 10)

    def test_retries_without_json_mode_on_error(self) -> None:
        llm, models = _client(ValueError("mime not supported"), SimpleNamespace(text="plain", candidates=[]))
        self.assertEqual(llm.generate_text("hi"), "plain")
        self.assertEqual(len(models.calls), 2)
        self.assertIsNone(models.calls[1]["config"].response_mime_type)

    def test_error_without_json_mode_propagates(self) -> None:
        llm, _ = _client(ValueError("boom"))
        with self.assertRaises(ValueError):
            llm.generate_text("hi", GeminiGenerationConfig(response_mime_type=None))

    def test_falls_back_to_candidate_parts(self) -> None:
        parts = [SimpleNamespace(text="a"), SimpleNamespace(text=None), SimpleNamespace(text="b")]
        resp = SimpleNamespace(text=None, candidates=[SimpleNamespace(content=SimpleNamespace(parts=parts))])
        llm, _ = _client(resp)
        self.assertEqual(llm.generate_text("hi"), "ab")

    def test_empty_response_raises(self) -> None:
        llm, _ = _client(SimpleNamespace(text=None, candidates=None))
        with self.assertRaises(RuntimeError):
            llm.generate_text("hi")


if __name__ == "__main__":
    unittest.main()
