from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import PreferenceNormalizer, UserPreferences
from zomato_ai.phase2.selector import DeterministicCandidateSelector
from zomato_ai.phase3.env_config import get_gemini_model_name
from zomato_ai.phase3.gemini_client import GeminiGenerationConfig, GeminiLlmClient
from zomato_ai.phase3.llm_output_parser import parse_json_object
from zomato_ai.phase3.llm_output_validator import dataframe_by_id, validate_llm_payload
from zomato_ai.phase3.prompt_builder import PromptBuilder
from zomato_ai.phase3.prompt_contract import (
    JSON_SYSTEM_INSTRUCTION,
    PROMPT_VERSION,
    format_estimated_cost,
)


@dataclass(frozen=True)
class OrchestratorResult:
    recommendations: List[Dict[str, Any]]
    used_fallback: bool
    llm_model: str
    prompt_version: str
    candidate_count: int
    total_after_filters: int
    error: Optional[str] = None


class RecommendationOrchestrator:
    """
    Phase 3: deterministic candidates (Phase 2) + Gemini ranking + explanations.
    """

    def __init__(
        self,
        catalog: RestaurantCatalog,
        *,
        llm_client: Optional[GeminiLlmClient] = None,
        generate_fn: Optional[Callable[[str], str]] = None,
        prompt_builder: Optional[PromptBuilder] = None,
        selector_top_k: int = 30,
    ):
        self._catalog = catalog
        self._selector = DeterministicCandidateSelector(catalog)
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._llm = llm_client
        self._generate_fn = generate_fn
        self._selector_top_k = selector_top_k
        self._lazy_gemini: Optional[GeminiLlmClient] = None

    def _get_gemini(self) -> GeminiLlmClient:
        if self._llm is not None:
            return self._llm
        if self._lazy_gemini is None:
            self._lazy_gemini = GeminiLlmClient(system_instruction=JSON_SYSTEM_INSTRUCTION)
        return self._lazy_gemini

    def _generate(self, prompt: str, config: Optional[GeminiGenerationConfig] = None) -> str:
        if self._generate_fn is not None:
            return self._generate_fn(prompt)
        return self._get_gemini().generate_text(prompt, config)

    def _parse_merge(
        self,
        raw_text: str,
        allowed_ids: set,
        sel_candidates: pd.DataFrame,
        result_limit: int,
    ) -> List[Dict[str, Any]]:
        data = parse_json_object(raw_text)
        payload, _ = validate_llm_payload(
            data,
            allowed_ids=allowed_ids,
            max_rank=max(len(allowed_ids), 1),
        )
        return _merge_llm_payload(payload, sel_candidates, result_limit)

    def recommend(
        self,
        prefs: UserPreferences,
        *,
        location_match_mode: Optional[str] = None,
        result_limit: int = 10,
    ) -> OrchestratorResult:
        normalized = PreferenceNormalizer.normalize(prefs, location_match_mode=location_match_mode)
        sel = self._selector.select(normalized, top_k=self._selector_top_k)
        if sel.candidates.empty:
            return OrchestratorResult(
                recommendations=[],
                used_fallback=False,
                llm_model=get_gemini_model_name(),
                prompt_version=PROMPT_VERSION,
                candidate_count=0,
                total_after_filters=0,
                error="no_candidates",
            )

        allowed_ids = set(sel.candidates["restaurant_id"].astype(str).str.strip())
        allowed_ids.discard("")

        model_name = get_gemini_model_name()
        rank_cfg = GeminiGenerationConfig(
            temperature=0.2,
            max_output_tokens=4096,
            response_mime_type="application/json",
        )
        repair_cfg = GeminiGenerationConfig(
            temperature=0.0,
            max_output_tokens=4096,
            response_mime_type="application/json",
        )

        last_raw = ""
        first_err: Optional[Exception] = None

        def ok(merged: List[Dict[str, Any]]) -> OrchestratorResult:
            return OrchestratorResult(
                recommendations=merged,
                used_fallback=False,
                llm_model=model_name,
                prompt_version=PROMPT_VERSION,
                candidate_count=len(sel.candidates),
                total_after_filters=sel.total_after_filters,
            )

        # 1) Primary prompt
        try:
            p1 = self._prompt_builder.build_ranking_prompt(
                normalized, sel.candidates, strict_json_retry=False
            )
            last_raw = self._generate(p1, rank_cfg)
            merged = self._parse_merge(last_raw, allowed_ids, sel.candidates, result_limit)
            return ok(merged)
        except Exception as e:
            first_err = e

        # 2) Stricter user prompt (retry)
        try:
            p2 = self._prompt_builder.build_ranking_prompt(
                normalized, sel.candidates, strict_json_retry=True
            )
            last_raw = self._generate(p2, rank_cfg)
            merged = self._parse_merge(last_raw, allowed_ids, sel.candidates, result_limit)
            return ok(merged)
        except Exception:
            pass

        # 3) Repair pass on the last model output
        try:
            repair_in = last_raw
            p3 = self._prompt_builder.build_json_repair_prompt(repair_in)
            last_raw = self._generate(p3, repair_cfg)
            merged = self._parse_merge(last_raw, allowed_ids, sel.candidates, result_limit)
            if not merged:
                raise ValueError("repair returned empty recommendations")
            return ok(merged)
        except Exception:
            pass

        fb = _fallback_deterministic(sel.candidates, result_limit)
        return OrchestratorResult(
            recommendations=fb,
            used_fallback=True,
            llm_model=model_name,
            prompt_version=PROMPT_VERSION,
            candidate_count=len(sel.candidates),
            total_after_filters=sel.total_after_filters,
            error=str(first_err) if first_err else "llm_parse_failed",
        )


def _merge_llm_payload(payload, candidates_df: pd.DataFrame, result_limit: int) -> List[Dict[str, Any]]:
    by_id = dataframe_by_id(candidates_df)
    rows = sorted(payload.recommendations, key=lambda r: r.rank)
    out: List[Dict[str, Any]] = []
    seen_names: set = set()
    for r in rows:
        base = by_id.get(r.restaurant_id)
        if not base:
            continue
        name_key = str(base.get("name", "")).strip().casefold()
        if name_key and name_key in seen_names:
            continue
        row = {
            "rank": r.rank,
            "restaurant_id": r.restaurant_id,
            "name": base.get("name"),
            "location": base.get("location"),
            "cuisine": base.get("cuisine"),
            "dish_liked": base.get("dish_liked"),
            "rating": float(pd.to_numeric(base.get("rating"), errors="coerce") or 0.0),
            "estimated_cost": format_estimated_cost(base),
            "explanation": r.explanation,
        }
        out.append(row)
        if name_key:
            seen_names.add(name_key)
        if len(out) >= result_limit:
            break
    return out


def _fallback_deterministic(candidates_df: pd.DataFrame, result_limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen_names: set = set()
    for i, (_, row) in enumerate(candidates_df.head(result_limit).iterrows(), start=1):
        name_key = str(row.get("name", "")).strip().casefold()
        if name_key and name_key in seen_names:
            continue
        rating = float(pd.to_numeric(row.get("rating"), errors="coerce") or 0.0)
        cost = format_estimated_cost(row) or ""
        cuisine = str(row.get("cuisine", ""))
        loc = str(row.get("location", ""))
        expl = (
            f"Matched using your filters (location {loc}, cuisine signals, min rating, budget/cost). "
            f"Rating {rating:.1f}/5; cost {cost}. Cuisine: {cuisine[:120]}."
        )
        out.append(
            {
                "rank": i,
                "restaurant_id": str(row.get("restaurant_id", "")),
                "name": row.get("name"),
                "location": row.get("location"),
                "cuisine": row.get("cuisine"),
                "dish_liked": row.get("dish_liked"),
                "rating": rating,
                "estimated_cost": format_estimated_cost(row),
                "explanation": expl,
            }
        )
        if name_key:
            seen_names.add(name_key)
    return out
