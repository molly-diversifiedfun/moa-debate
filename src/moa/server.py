"""FastAPI HTTP server for n8n webhook integration."""

import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional

from .engine import run_moa, run_expert_review, run_debate, run_cascade
from .budget import get_spend_summary


class MoaRequest(BaseModel):
    query: str
    tier: str = "lite"


class CascadeRequest(BaseModel):
    query: str
    lite_tier: str = "lite"
    premium_tier: str = "ultra"


class ReviewRequest(BaseModel):
    diff: str
    context: str = ""


class DebateRequest(BaseModel):
    query: str
    rounds: int = Field(default=2, ge=1, le=5)
    tier: str = "pro"


class MoaResponse(BaseModel):
    response: str
    latency_ms: int
    cost_usd: float
    models_used: list
    escalated: bool = False
    escalation_reason: Optional[str] = None
    warning: Optional[str] = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="MoA Debate System",
        description="Multi-model AI — MoA, Expert Panel, Cascade, and Debate",
        version="0.3.0",
    )

    # ── Auth middleware ─────────────────────────────────────────────────────
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Require X-MOA-Key header on all endpoints except /health."""
        server_key = os.environ.get("MOA_SERVER_KEY")

        # If no key is configured, skip auth (dev mode)
        if server_key and request.url.path != "/health":
            req_key = request.headers.get("X-MOA-Key", "")
            if req_key != server_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing X-MOA-Key header"},
                )

        return await call_next(request)

    @app.get("/health")
    async def health():
        from .models import TIERS, available_models
        budget = get_spend_summary()
        return {
            "status": "ok",
            "available_models": len(available_models()),
            "tiers": {
                name: len(tier.available_proposers)
                for name, tier in TIERS.items()
            },
            "budget": budget,
        }

    @app.post("/moa", response_model=MoaResponse)
    async def moa_endpoint(req: MoaRequest):
        try:
            result = await run_moa(req.query, req.tier)
            return MoaResponse(
                response=result["response"],
                latency_ms=result["latency_ms"],
                cost_usd=result["cost"].estimated_cost_usd,
                models_used=result["cost"].models_used,
                warning=result.get("warning"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/cascade", response_model=MoaResponse)
    async def cascade_endpoint(req: CascadeRequest):
        try:
            result = await run_cascade(req.query, req.lite_tier, req.premium_tier)
            return MoaResponse(
                response=result["response"],
                latency_ms=result["latency_ms"],
                cost_usd=result["cost"].estimated_cost_usd,
                models_used=result["cost"].models_used,
                escalated=result["cost"].escalated,
                escalation_reason=result.get("escalation_reason"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/review", response_model=MoaResponse)
    async def review_endpoint(req: ReviewRequest):
        try:
            result = await run_expert_review(req.diff, req.context)
            return MoaResponse(
                response=result["response"],
                latency_ms=result["latency_ms"],
                cost_usd=result["cost"].estimated_cost_usd,
                models_used=result["cost"].models_used,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/debate", response_model=MoaResponse)
    async def debate_endpoint(req: DebateRequest):
        try:
            result = await run_debate(req.query, rounds=req.rounds, tier_name=req.tier)
            return MoaResponse(
                response=result["response"],
                latency_ms=result["latency_ms"],
                cost_usd=result["cost"].estimated_cost_usd,
                models_used=result["cost"].models_used,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return app
