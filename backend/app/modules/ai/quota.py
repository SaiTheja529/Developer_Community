"""AI availability, budget and per-user quotas (spec §9.10)."""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.common.errors import ApiError
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.ai.models import AIUsage
from app.modules.ai.usage import GENERATION_FEATURES

_COST_CACHE_TTL = 60
_cost_cache: dict = {"value": None, "at": 0.0}
_lock = threading.Lock()
STAFF_MULTIPLIER = 5


def _month_start(now: datetime) -> datetime:
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start(now: datetime) -> datetime:
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def next_utc_midnight(now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    return _day_start(now) + timedelta(days=1)


def month_to_date_cost(use_cache: bool = True) -> float:
    with _lock:
        if use_cache and _cost_cache["value"] is not None and time.monotonic() - _cost_cache["at"] < _COST_CACHE_TTL:
            return _cost_cache["value"]
    now = datetime.now(UTC)
    value = float(
        db.session.execute(
            select(func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0)).where(AIUsage.created_at >= _month_start(now))
        ).scalar_one()
    )
    with _lock:
        _cost_cache.update(value=value, at=time.monotonic())
    return value


def reset_cost_cache() -> None:
    with _lock:
        _cost_cache.update(value=None, at=0.0)


def ai_status_reason() -> str | None:
    s = get_settings()
    if not s.AI_ENABLED:
        return "disabled"
    try:
        if month_to_date_cost() >= s.AI_MONTHLY_BUDGET_USD:
            return "budget_exhausted"
    except Exception:  # pragma: no cover - DB issues should not break /meta/config
        db.session.rollback()
    return None


def _limits(user) -> tuple[int, int]:
    s = get_settings()
    mult = STAFF_MULTIPLIER if user.role in ("moderator", "admin") else 1
    return s.AI_DAILY_TOKEN_LIMIT * mult, s.AI_DAILY_GENERATION_LIMIT * mult


def user_today(user) -> dict:
    now = datetime.now(UTC)
    start = _day_start(now)
    tokens, generations = db.session.execute(
        select(
            func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
            func.count().filter(AIUsage.feature.in_(GENERATION_FEATURES), AIUsage.outcome == "success"),
        ).where(AIUsage.user_id == user.id, AIUsage.created_at >= start)
    ).one()
    limit_tokens, limit_generations = _limits(user)
    return {
        "tokens": int(tokens),
        "generations": int(generations),
        "limit_tokens": limit_tokens,
        "limit_generations": limit_generations,
        "resets_at": next_utc_midnight(now),
    }


def ensure_ai_allowed(user, generation: bool) -> None:
    """Checks 1-4 of §9.10. Rate limits (step 5) are applied by the caller afterwards."""
    reason = ai_status_reason()
    if reason == "disabled":
        raise ApiError("ai_unavailable", "AI features are turned off right now.", 503, {"reason": "disabled"})
    if reason == "budget_exhausted":
        raise ApiError("ai_unavailable", "AI features are paused for the rest of the month.", 503,
                       {"reason": "budget_exhausted"})
    today = user_today(user)
    if today["tokens"] >= today["limit_tokens"]:
        raise ApiError(
            "ai_quota_exceeded", "You've reached today's AI limit.", 429,
            {"resets_at": today["resets_at"].isoformat().replace("+00:00", "Z"), "limit": "tokens"},
        )
    if generation and today["generations"] >= today["limit_generations"]:
        raise ApiError(
            "ai_quota_exceeded", "You've reached today's AI generation limit.", 429,
            {"resets_at": today["resets_at"].isoformat().replace("+00:00", "Z"), "limit": "generations"},
        )
