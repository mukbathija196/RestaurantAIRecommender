from __future__ import annotations

import json
from typing import List

import pandas as pd

from zomato_ai.phase2.preferences import UserPreferencesNormalized
from zomato_ai.phase3.prompt_contract import (
    MAX_CANDIDATES_IN_PROMPT,
    MAX_CUISINE_LEN,
    MAX_NAME_LEN,
    PROMPT_VERSION,
    CandidateForPrompt,
    GROUNDING_RULES,
)


class PromptBuilder:
    def build_ranking_prompt(
        self,
        prefs: UserPreferencesNormalized,
        candidates_df: pd.DataFrame,
        *,
        max_candidates: int = MAX_CANDIDATES_IN_PROMPT,
        strict_json_retry: bool = False,
    ) -> str:
        """
        User message: preferences + candidates + task.
        System-level JSON rules should be supplied via Gemini `system_instruction` (see JSON_SYSTEM_INSTRUCTION).
        """
        rows = candidates_df.head(int(max_candidates))
        candidates: List[CandidateForPrompt] = []
        for _, r in rows.iterrows():
            name = str(r.get("name", ""))[:MAX_NAME_LEN]
            cuisine = str(r.get("cuisine", ""))[:MAX_CUISINE_LEN]
            rid = str(r.get("restaurant_id", "")).strip()
            if not rid:
                continue
            candidates.append(
                CandidateForPrompt(
                    restaurant_id=rid,
                    name=name,
                    location=str(r.get("location", ""))[:80],
                    cuisine=cuisine,
                    dish_liked=str(r.get("dish_liked", ""))[:200],
                    rating=float(pd.to_numeric(r.get("rating"), errors="coerce") or 0.0),
                    cost_bucket=str(r.get("cost_bucket", "")),
                )
            )

        user_preferences = {
            "cuisines": prefs.cuisines,
            "min_rating": prefs.min_rating,
            "extra_preferences": prefs.extra_preferences,
        }
        if prefs.location_norm:
            user_preferences["location"] = prefs.location
        if prefs.allowed_cost_buckets:
            user_preferences["budget"] = prefs.budget

        payload = {
            "prompt_version": PROMPT_VERSION,
            "user_preferences": user_preferences,
            "candidates": [c.model_dump() for c in candidates],
        }

        schema = {
            "recommendations": [
                {
                    "rank": 1,
                    "restaurant_id": "must be one of candidate restaurant_id values",
                    "explanation": "short paragraph grounded in candidate fields",
                }
            ]
        }

        extra = ""
        if strict_json_retry:
            extra = (
                "\n\nRETRY — OUTPUT FORMAT IS STRICT:\n"
                "- Output a single JSON object only.\n"
                "- Do NOT include markdown fences, headings, bullets, or any text outside JSON.\n"
                "- Do NOT include keys other than the top-level object with \"recommendations\".\n"
            )

        return (
            f"{GROUNDING_RULES}\n\n"
            "Reminder: Your entire reply must be parseable JSON (no prose). "
            "Schema shape:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Ranking rules:\n"
            "- Prefer higher ratings when aligned with cuisine preferences.\n"
            "- Respect cost_bucket alignment with the user's budget.\n"
            "- Prefer location match when relevant.\n"
            f"{extra}\n"
            "Input JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def build_json_repair_prompt(self, malformed_output: str, *, max_chars: int = 12000) -> str:
        """
        Third pass: ask the model to emit valid JSON only, given noisy output.
        """
        truncated = (malformed_output or "").strip()
        if len(truncated) > max_chars:
            truncated = truncated[:max_chars] + "\n... [truncated]"

        schema = {
            "recommendations": [
                {
                    "rank": 1,
                    "restaurant_id": "string",
                    "explanation": "string",
                }
            ]
        }

        return (
            "You fix malformed model outputs.\n\n"
            "Task: From the text below, output ONLY one valid JSON object matching exactly this shape:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            "Rules:\n"
            "- Output JSON only. No markdown. No commentary.\n"
            "- Copy restaurant_id values exactly as they appear in the text.\n"
            "- If multiple restaurants exist, pick the best ordering you can infer from the text.\n"
            "- If the text cannot be recovered, return {\"recommendations\":[]}.\n\n"
            "Malformed text:\n"
            "---\n"
            f"{truncated}\n"
            "---"
        )
