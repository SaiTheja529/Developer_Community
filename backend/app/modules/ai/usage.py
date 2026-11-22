"""AI usage recording and cost estimation (spec §9.9). Never stores prompts or outputs."""

from __future__ import annotations

import logging
from decimal import Decimal

from flask import g

from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.ai.models import AIUsage

log = logging.getLogger("devcommons.ai.usage")

GENERATION_FEATURES = (
    "generate_harness",
    "generate_idea",
    "generate_resources",
    "refine",
    "refine_section",
    "feedback_suggestions",
)


def estimate_cost(model: str, input_tokens: int, cached_input_tokens: int, output_tokens: int, pricing: dict | None = None) -> Decimal:
    pricing = pricing if pricing is not None else get_settings().AI_PRICING_JSON
    prices = pricing.get(model)
    if prices is None:
        if model and model != "fake-model":
            log.warning("ai_model_missing_from_pricing", extra={"model": model})
        return Decimal("0")
    uncached = max(input_tokens - cached_input_tokens, 0)
    cost = (
        Decimal(uncached) * Decimal(str(prices.get("input_per_1m", 0)))
        + Decimal(cached_input_tokens) * Decimal(str(prices.get("cached_input_per_1m", 0)))
        + Decimal(output_tokens) * Decimal(str(prices.get("output_per_1m", 0)))
    ) / Decimal(1_000_000)
    return cost.quantize(Decimal("0.000001"))


def record_usage(
    *,
    user_id,
    feature: str,
    model: str,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: int | None = None,
    outcome: str = "success",
    error_code: str | None = None,
    commit: bool = True,
) -> None:
    row = AIUsage(
        user_id=user_id,
        feature=feature,
        model=model or "unknown",
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        estimated_cost_usd=estimate_cost(model or "", input_tokens, cached_input_tokens, output_tokens),
        latency_ms=latency_ms,
        outcome=outcome,
        error_code=error_code,
        request_id=g.get("request_id"),
    )
    db.session.add(row)
    log.info(
        "ai_call",
        extra={
            "feature": feature,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "outcome": outcome,
            "error_code": error_code,
        },
    )
    if commit:
        db.session.commit()
