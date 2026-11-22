"""/api/internal/jobs/* — triggered by a scheduler with X-Job-Secret (spec §8.14)."""

from __future__ import annotations

import functools
import hmac

from flask import Blueprint, request

from app.common.errors import ApiError
from app.common.responses import ok
from app.extensions import limiter
from app.extensions import settings as get_settings
from app.modules.jobs import service

bp = Blueprint("jobs", __name__, url_prefix="/api/internal/jobs")
limiter.exempt(bp)


def require_job_secret(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        provided = request.headers.get("X-Job-Secret", "")
        expected = get_settings().JOB_SECRET
        if not provided or not hmac.compare_digest(provided.encode(), expected.encode()):
            raise ApiError("unauthenticated", "Invalid job secret.", 401)
        return fn(*args, **kwargs)

    return wrapper


def _run(name: str, fn):
    with service.advisory_lock(name) as acquired:
        if not acquired:
            return ok({"job": name, "skipped": True, "reason": "already_running"})
        return ok({"job": name, "skipped": False, "result": fn()})


@bp.post("/link-check")
@require_job_secret
def link_check():
    return _run("link-check", service.link_check)


@bp.post("/refresh-repos")
@require_job_secret
def refresh_repos():
    return _run("refresh-repos", service.refresh_repos)


@bp.post("/cleanup")
@require_job_secret
def cleanup():
    return _run("cleanup", service.cleanup)


@bp.post("/rebuild-counters")
@require_job_secret
def rebuild_counters():
    return _run("rebuild-counters", service.rebuild_counters)
