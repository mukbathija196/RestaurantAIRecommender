from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from zomato_ai.phase3.env_config import get_gemini_model_name, require_gemini_api_key


@dataclass
class GeminiGenerationConfig:
    temperature: float = 0.2
    max_output_tokens: int = 4096
    # When set, asks Gemini to return JSON (supported on recent Gemini models).
    response_mime_type: Optional[str] = "application/json"


class GeminiLlmClient:
    """
    Thin wrapper around google-generativeai for Phase 3.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        system_instruction: Optional[str] = None,
    ):
        key = api_key or require_gemini_api_key()
        genai.configure(api_key=key)
        self._model_name = model_name or get_gemini_model_name()
        kwargs = {}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        try:
            self._model = genai.GenerativeModel(self._model_name, **kwargs)
        except TypeError:
            self._model = genai.GenerativeModel(self._model_name)

    def generate_text(self, prompt: str, config: Optional[GeminiGenerationConfig] = None) -> str:
        cfg = config or GeminiGenerationConfig()
        gen_config: dict = {
            "temperature": cfg.temperature,
            "max_output_tokens": cfg.max_output_tokens,
        }
        if cfg.response_mime_type:
            gen_config["response_mime_type"] = cfg.response_mime_type

        try:
            response = self._model.generate_content(prompt, generation_config=gen_config)
        except Exception:
            if cfg.response_mime_type:
                gen_config.pop("response_mime_type", None)
                response = self._model.generate_content(prompt, generation_config=gen_config)
            else:
                raise

        text = getattr(response, "text", None)
        if text:
            return text
        if response.candidates:
            parts = response.candidates[0].content.parts
            return "".join(getattr(p, "text", "") for p in parts)
        raise RuntimeError("Gemini returned no text (check safety filters or prompt).")
