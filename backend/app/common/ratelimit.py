"""Rate limiting helpers (spec §13).

Flask-Limiter applies the default 300/min per IP. Route-specific limits are enforced
explicitly with `enforce()` *after* authentication, so they can be keyed by user ID.
They share Flask-Limiter's storage (memory in dev, Redis in prod).
"""

from __future__ import annotations

import functools
import math
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from flask import current_app, g, request
from limits import parse

from app.common.errors import rate_limited


def client_ip() -> str:
    # ProxyFix (configured via TRUST_PROXY_HOPS) already rewrote remote_addr from X-Forwarded-For.
    return request.remote_addr or "unknown"


def user_or_ip() -> str:
    user = getattr(g, "current_user", None)
    return f"user:{user.id}" if user is not None else f"ip:{client_ip()}"


def enforce(limit: str, scope: str, key: str | None = None) -> None:
    """Consume one hit for `limit` under `scope`/`key`; raise 429 rate_limited if exceeded."""
    if not current_app.config.get("RATELIMIT_ENABLED", True):
        return
    from app.extensions import limiter

    item = parse(limit)
    identity = key or user_or_ip()
    strategy = limiter.limiter
    if not strategy.hit(item, "dc", scope, identity):
        stats = strategy.get_window_stats(item, "dc", scope, identity)
        retry = max(1, math.ceil(stats.reset_time - time.time()))
        raise rate_limited(retry)


def is_new_account() -> bool:
    user = getattr(g, "current_user", None)
    if user is None or user.created_at is None:
        return False
    created = user.created_at if user.created_at.tzinfo else user.created_at.replace(tzinfo=UTC)
    return datetime.now(UTC) - created < timedelta(hours=24)


def limit(spec: str | Callable[[], str], scope: str, key: Callable[[], str] | None = None):
    """Decorator applying `enforce` before the view body. Place it *below* auth decorators."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            value = spec() if callable(spec) else spec
            enforce(value, scope, key() if key else None)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def creation_limit() -> str:
    """10/hour per user; new accounts (< 24 h) get half (spec §13)."""
    return "5 per hour" if is_new_account() else "10 per hour"
