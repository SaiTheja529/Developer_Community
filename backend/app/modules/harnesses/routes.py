"""/api/harnesses, /api/reviews and /api/github endpoints (spec §8.3, §8.12)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common.content import get_or_404
from app.common.pagination import paginate
from app.common.ratelimit import creation_limit, limit
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import QueryModel, parse_body, validate_query
from app.extensions import db
from app.modules.harnesses import service
from app.modules.harnesses.models import Harness
from app.modules.harnesses.schemas import (
    HarnessCreate,
    HarnessListQuery,
    HarnessUpdate,
    ReviewCreate,
    ReviewListQuery,
    ReviewUpdate,
)

bp = Blueprint("harnesses", __name__, url_prefix="/api/harnesses")
reviews_bp = Blueprint("reviews", __name__, url_prefix="/api/reviews")
github_bp = Blueprint("github", __name__, url_prefix="/api/github")


@bp.get("")
@optional_auth
@validate_query(HarnessListQuery)
def list_harnesses(query: HarnessListQuery):
    page = paginate(service.list_harnesses(query, g.current_user), query.page, query.page_size)
    return paginated(service.summaries(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.post("")
@require_auth
@require_verified
@limit(creation_limit, "create_harness")
def create_harness():
    body = parse_body(HarnessCreate)
    h = service.create(g.current_user, body)
    return created(service.detail(h, g.current_user))


@bp.get("/<uuid:harness_id>")
@optional_auth
def get_harness(harness_id: uuid.UUID):
    h = get_or_404(Harness, harness_id, g.current_user)
    return ok(service.detail(h, g.current_user))


@bp.patch("/<uuid:harness_id>")
@require_auth
@require_verified
def update_harness(harness_id: uuid.UUID):
    body = parse_body(HarnessUpdate)
    h = service.get_for_owner(harness_id, g.current_user)
    h = service.update_harness(h, g.current_user, body)
    return ok(service.detail(h, g.current_user))


@bp.delete("/<uuid:harness_id>")
@require_auth
@require_verified
def delete_harness(harness_id: uuid.UUID):
    service.soft_delete(harness_id, g.current_user)
    return no_content()


@bp.post("/<uuid:harness_id>/refresh-repo")
@require_auth
@require_verified
def refresh_repo(harness_id: uuid.UUID):
    from app.common.ratelimit import enforce

    h = service.get_for_owner(harness_id, g.current_user)
    db.session.rollback()  # release the row lock while we call GitHub
    enforce("1 per 10 minutes", "harness_refresh_repo", key=f"harness:{harness_id}")
    h = get_or_404(Harness, harness_id, g.current_user)
    h = service.refresh_repo(h)
    return ok(service.detail(h, g.current_user))


# Reviews ----------------------------------------------------------------------------------


@bp.get("/<uuid:harness_id>/reviews")
@optional_auth
@validate_query(ReviewListQuery)
def list_reviews(harness_id: uuid.UUID, query: ReviewListQuery):
    get_or_404(Harness, harness_id, g.current_user)
    page = paginate(service.list_reviews_stmt(harness_id, g.current_user, query.sort), query.page, query.page_size)
    return paginated(service.review_dicts(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.post("/<uuid:harness_id>/reviews")
@require_auth
@require_verified
@limit("20 per hour", "create_review")
def create_review(harness_id: uuid.UUID):
    body = parse_body(ReviewCreate)
    r = service.create_review(harness_id, g.current_user, body)
    return created(service.review_dicts([r], g.current_user)[0])


@reviews_bp.patch("/<uuid:review_id>")
@require_auth
@require_verified
def update_review(review_id: uuid.UUID):
    body = parse_body(ReviewUpdate)
    r = service.get_review_for_edit(review_id, g.current_user, allow_mod=True)
    r = service.update_review(r, body)
    return ok(service.review_dicts([r], g.current_user)[0])


@reviews_bp.delete("/<uuid:review_id>")
@require_auth
@require_verified
def delete_review(review_id: uuid.UUID):
    r = service.get_review_for_edit(review_id, g.current_user, allow_mod=True)
    service.delete_review(r)
    return no_content()


# GitHub preview ---------------------------------------------------------------------------


class RepoPreviewQuery(QueryModel):
    url: str = ""


@github_bp.get("/repo-preview")
@require_auth
@limit("20 per minute", "github_preview")
@validate_query(RepoPreviewQuery)
def repo_preview(query: RepoPreviewQuery):
    from app.integrations.github import fetch_repo_for_submission

    ref, meta = fetch_repo_for_submission(query.url)
    existing = service.find_by_repo(ref.owner, ref.repo)
    already = None
    if existing is not None and existing.status == "published":
        already = service.summaries([existing], g.current_user)[0]
    return ok(
        {
            "owner": ref.owner,
            "repo": ref.repo,
            "canonical_url": ref.canonical_url,
            "description": meta.get("description"),
            "stars": meta.get("stars"),
            "language": meta.get("language"),
            "license": meta.get("license"),
            "topics": meta.get("topics", []),
            "pushed_at": meta.get("pushed_at"),
            "archived": meta.get("archived", False),
            "already_listed": already,
        }
    )
