from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from zomato_ai.phase1.catalog import RestaurantCatalog
from zomato_ai.phase2.preferences import UserPreferences
from zomato_ai.phase3.env_config import load_env_from_dotenv, require_gemini_api_key
from zomato_ai.phase3.orchestrator import RecommendationOrchestrator
from zomato_ai.phase4.paths import resolve_processed_artifact_path
from zomato_ai.phase4.schemas import (
    RecommendMeta,
    RecommendRequest,
    RecommendResponse,
    RecommendationItem,
    UiOptionsResponse,
)

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _dry_generate(_prompt: str) -> str:
    raise RuntimeError("dry-run")


def _split_city_locality(location: str) -> Tuple[str, str]:
    parts = [p.strip() for p in str(location).split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-1], ", ".join(parts[:-1])
    return "Bengaluru", str(location).strip()


def _load_budget_thresholds(path: str) -> Tuple[float, float]:
    metadata_path = Path(path).with_name("metadata.json")
    if not metadata_path.exists():
        return 500.0, 1500.0
    try:
        import json

        raw = json.loads(metadata_path.read_text())
        thresholds = raw.get("cost_bucket_thresholds", {})
        q1 = float(thresholds.get("q1", 500.0))
        q2 = float(thresholds.get("q2", 1500.0))
        return (q1, q2) if q2 >= q1 else (q2, q1)
    except Exception:
        return 500.0, 1500.0


def _build_ui_options(df: pd.DataFrame, q1: float, q2: float) -> UiOptionsResponse:
    by_city: Dict[str, set] = {}
    for location in sorted(df["location"].dropna().astype(str).unique()):
        city, locality = _split_city_locality(location)
        by_city.setdefault(city, set()).add(locality or location)

    localities_by_city = {city: sorted(vals) for city, vals in sorted(by_city.items())}
    cities = sorted(localities_by_city.keys())

    cuisines: set = set()
    cuisine_counts: Dict[str, int] = {}
    for raw in df["cuisine"].dropna().astype(str):
        for token in raw.split(","):
            clean = token.strip()
            if clean:
                cuisines.add(clean)
                cuisine_counts[clean] = cuisine_counts.get(clean, 0) + 1

    ordered_cuisines = [
        k for k, _ in sorted(cuisine_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    budget_bands: Dict[str, Dict[str, Optional[float]]] = {
        "0-1000": {"min": 0.0, "max": 1000.0},
        "1001-2000": {"min": 1001.0, "max": 2000.0},
        "2001-3000": {"min": 2001.0, "max": 3000.0},
        "3001-4000": {"min": 3001.0, "max": 4000.0},
        "4001-5000": {"min": 4001.0, "max": 5000.0},
    }

    return UiOptionsResponse(
        cities=cities,
        localities_by_city=localities_by_city,
        cuisines=ordered_cuisines,
        popular_cuisines=ordered_cuisines[:6],
        budget_bands=budget_bands,
    )


def _budget_buckets_from_range(
    budget_min: Optional[float],
    budget_max: Optional[float],
    q1: float,
    q2: float,
) -> List[str]:
    if budget_min is None and budget_max is None:
        return []
    lo = float(budget_min if budget_min is not None else 0.0)
    hi = float(budget_max if budget_max is not None else 10_000_000.0)
    if hi < lo:
        lo, hi = hi, lo

    bands = {
        "low": (0.0, q1),
        "medium": (q1, q2),
        "high": (q2, float("inf")),
    }
    out: List[str] = []
    for key, (b_lo, b_hi) in bands.items():
        if hi >= b_lo and lo <= b_hi:
            out.append(key)
    return out


def create_app(*, injected_orchestrator: Optional[RecommendationOrchestrator] = None) -> FastAPI:
    """
    FastAPI application factory.

    `injected_orchestrator` is used by tests; production uses catalog loaded from disk.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if injected_orchestrator is not None:
            app.state.orchestrator = injected_orchestrator
            app.state.artifact_path = "injected"
            app.state.catalog = injected_orchestrator._catalog
            app.state.budget_q1 = 500.0
            app.state.budget_q2 = 1500.0
            app.state.ui_options = _build_ui_options(
                injected_orchestrator._catalog.to_dataframe(),
                app.state.budget_q1,
                app.state.budget_q2,
            )
        else:
            load_env_from_dotenv()
            dry = os.getenv("RECOMMENDATIONS_DRY_RUN", "").lower() in ("1", "true", "yes")
            if not dry:
                require_gemini_api_key()
            path = resolve_processed_artifact_path()
            if not Path(path).exists():
                raise RuntimeError(f"Processed artifact not found: {path}")
            catalog = RestaurantCatalog(Path(path))
            if dry:
                orch = RecommendationOrchestrator(catalog, generate_fn=_dry_generate)
            else:
                orch = RecommendationOrchestrator(catalog)
            app.state.orchestrator = orch
            app.state.catalog = catalog
            app.state.artifact_path = path
            app.state.budget_q1, app.state.budget_q2 = _load_budget_thresholds(path)
            app.state.ui_options = _build_ui_options(
                catalog.to_dataframe(),
                app.state.budget_q1,
                app.state.budget_q2,
            )
        yield

    app = FastAPI(
        title="Zomato AI Recommendations",
        version="0.1.0",
        lifespan=lifespan,
    )

    origins = os.getenv("CORS_ORIGINS", "*").strip()
    if origins:
        if origins == "*":
            app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=False,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        else:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=[o.strip() for o in origins.split(",") if o.strip()],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

    @app.get("/health")
    def health(request: Request) -> dict:
        return {
            "status": "ok",
            "artifact_path": getattr(request.app.state, "artifact_path", None),
        }

    @app.get("/")
    def root() -> dict:
        return {
            "service": "zomato-ai-recommendations",
            "docs": "/docs",
            "ui": "/ui/",
            "recommendations": "POST /recommendations",
        }

    @app.get("/ui/options", response_model=UiOptionsResponse)
    def ui_options(request: Request) -> UiOptionsResponse:
        return request.app.state.ui_options

    @app.post("/recommendations", response_model=RecommendResponse)
    def recommendations(body: RecommendRequest, request: Request) -> RecommendResponse:
        orch: RecommendationOrchestrator = request.app.state.orchestrator
        location = (body.locality or body.location or "").strip()

        selected_budget = body.budget or "medium"
        budget_buckets = _budget_buckets_from_range(
            body.budget_min,
            body.budget_max,
            request.app.state.budget_q1,
            request.app.state.budget_q2,
        )
        prefs = UserPreferences(
            location=location,
            budget=selected_budget,
            allowed_cost_buckets=budget_buckets,
            cuisines=body.cuisines,
            min_rating=body.min_rating,
            extra_preferences=body.extra_preferences,
        )
        try:
            result = orch.recommend(
                prefs,
                location_match_mode=body.location_match,
                result_limit=body.limit,
            )
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail={"message": "Recommendation service failed", "error": str(e)},
            ) from e

        items = [
            RecommendationItem(
                rank=r["rank"],
                restaurant_id=str(r["restaurant_id"]),
                name=r.get("name"),
                location=r.get("location"),
                cuisine=str(r["cuisine"]) if r.get("cuisine") is not None else None,
                dish_liked=str(r["dish_liked"]) if r.get("dish_liked") is not None else None,
                rating=float(r["rating"]) if r.get("rating") is not None else None,
                estimated_cost=str(r["estimated_cost"]) if r.get("estimated_cost") is not None else None,
                explanation=str(r.get("explanation", "")),
            )
            for r in result.recommendations
        ]

        return RecommendResponse(
            request_id=str(uuid.uuid4()),
            recommendations=items,
            meta=RecommendMeta(
                candidate_count=result.candidate_count,
                total_after_filters=result.total_after_filters,
                used_fallback=result.used_fallback,
                llm_model=result.llm_model,
                prompt_version=result.prompt_version,
                error=result.error,
            ),
        )

    if _STATIC_DIR.is_dir():
        app.mount(
            "/ui",
            StaticFiles(directory=str(_STATIC_DIR), html=True),
            name="ui",
        )

    return app


app = create_app()
