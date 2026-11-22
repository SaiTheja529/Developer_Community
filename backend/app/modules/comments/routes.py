"""Comment routes. `make_comment_routes(target_type)` mounts the per-target endpoints (spec §8.8)."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, g

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common.content import TARGETS, get_or_404, model_for
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import enforce
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import StrictModel, Text, parse_body, validate_query
from app.modules.comments import service


class CommentCreate(StrictModel):
    body: Text(1, 10000)
    parent_id: uuid.UUID | None = None
    ai_assisted: bool = False


class CommentUpdate(StrictModel):
    body: Text(1, 10000)
    ai_assisted: bool = False


class CommentListQuery(PageParams):
    sort: Literal["oldest", "newest", "top"] = "oldest"


def _comment_rate_limits():
    enforce("10 per minute", "comments_min")
    enforce("200 per day", "comments_day")


def make_comment_routes(target_type: str) -> Blueprint:
    plural = TARGETS[target_type].plural
    bp = Blueprint(f"{target_type}_comments", __name__, url_prefix=f"/api/{plural}")

    @bp.get("/<uuid:target_id>/comments")
    @optional_auth
    @validate_query(CommentListQuery)
    def list_comments(target_id: uuid.UUID, query: CommentListQuery):
        get_or_404(model_for(target_type), target_id, g.current_user)
        page = paginate(
            service.top_level_stmt(target_type, target_id, g.current_user, query.sort), query.page, query.page_size
        )
        replies = service.inline_replies([c.id for c in page.items], g.current_user)
        return paginated(service.serialize(page.items, g.current_user, replies), page.page, page.page_size, page.total)

    @bp.post("/<uuid:target_id>/comments")
    @require_auth
    @require_verified
    def create_comment(target_id: uuid.UUID):
        _comment_rate_limits()
        body = parse_body(CommentCreate)
        c = service.create(target_type, target_id, g.current_user, body)
        return created(service.serialize([c], g.current_user)[0])

    return bp


bp = Blueprint("comments", __name__, url_prefix="/api/comments")


class RepliesQuery(PageParams):
    pass


@bp.get("/<uuid:comment_id>/replies")
@optional_auth
@validate_query(RepliesQuery)
def list_replies(comment_id: uuid.UUID, query: RepliesQuery):
    parent = service.get_comment_for_replies(comment_id, g.current_user)
    page = paginate(service.replies_stmt(parent.id, g.current_user), query.page, query.page_size)
    return paginated(service.serialize(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.patch("/<uuid:comment_id>")
@require_auth
@require_verified
def update_comment(comment_id: uuid.UUID):
    body = parse_body(CommentUpdate)
    c = service.update(comment_id, g.current_user, body)
    return ok(service.serialize([c], g.current_user)[0])


@bp.delete("/<uuid:comment_id>")
@require_auth
@require_verified
def delete_comment(comment_id: uuid.UUID):
    service.delete(comment_id, g.current_user)
    return no_content()
