from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google import genai
from google.genai import types

from zomato_ai.phase3.env_config import get_gemini_model_name, require_gemini_api_key


@dataclass
class GeminiGenerationConfig:
    temperature: float = 0.2
    max_output_tokens: int = 4096
    # When set, asks Gemini to return JSON (supported on recent Gemini models).
    response_mime_type: Optional[str] = "application/json"


class GeminiLlmClient:
    """
    Thin wrapper around the google-genai SDK for Phase 3.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        api_key: Optional[str] = None,
        system_instruction: Optional[str] = None,
        client: Optional[genai.Client] = None,
    ):
        self._client = client or genai.Client(api_key=api_key or require_gemini_api_key())
        self._model_name = model_name or get_gemini_model_name()
        self._system_instruction = system_instruction

    def _build_config(self, cfg: GeminiGenerationConfig, *, json_mode: bool) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            temperature=cfg.temperature,
            max_output_tokens=cfg.max_output_tokens,
            system_instruction=self._system_instruction,
            response_mime_type=cfg.response_mime_type if json_mode else None,
        )

    def generate_text(self, prompt: str, config: Optional[GeminiGenerationConfig] = None) -> str:
        cfg = config or GeminiGenerationConfig()
        json_mode = bool(cfg.response_mime_type)

        try:
            response = self._client.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=self._build_config(cfg, json_mode=json_mode),
            )
        except Exception:
            if json_mode:
                response = self._client.models.generate_content(
                    model=self._model_name,
                    contents=prompt,
                    config=self._build_config(cfg, json_mode=False),
                )
            else:
                raise

        text = getattr(response, "text", None)
        if text:
            return text
        if response.candidates:
            content = response.candidates[0].content
            parts = (content.parts if content else None) or []
            joined = "".join(getattr(p, "text", None) or "" for p in parts)
            if joined:
                return joined
        raise RuntimeError("Gemini returned no text (check safety filters or prompt).")
