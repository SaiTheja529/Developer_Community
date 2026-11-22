"""/api/ideas endpoints (spec §8.4)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common.content import get_or_404
from app.common.pagination import paginate
from app.common.ratelimit import creation_limit, limit
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import parse_body, validate_query
from app.modules.ideas import service
from app.modules.ideas.models import Idea
from app.modules.ideas.schemas import IdeaCreate, IdeaListQuery, IdeaUpdate

bp = Blueprint("ideas", __name__, url_prefix="/api/ideas")


@bp.get("")
@optional_auth
@validate_query(IdeaListQuery)
def list_ideas(query: IdeaListQuery):
    page = paginate(service.list_ideas(query, g.current_user), query.page, query.page_size)
    return paginated(service.summaries(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.post("")
@require_auth
@require_verified
@limit(creation_limit, "create_idea")
def create_idea():
    body = parse_body(IdeaCreate)
    idea = service.create(g.current_user, body)
    return created(service.detail(idea, g.current_user))


@bp.get("/<uuid:idea_id>")
@optional_auth
def get_idea(idea_id: uuid.UUID):
    return ok(service.detail(get_or_404(Idea, idea_id, g.current_user), g.current_user))


@bp.patch("/<uuid:idea_id>")
@require_auth
@require_verified
def update_idea(idea_id: uuid.UUID):
    body = parse_body(IdeaUpdate)
    idea = service.update_idea(service.get_for_owner(idea_id, g.current_user), body)
    return ok(service.detail(idea, g.current_user))


@bp.delete("/<uuid:idea_id>")
@require_auth
@require_verified
def delete_idea(idea_id: uuid.UUID):
    service.soft_delete(idea_id, g.current_user)
    return no_content()
