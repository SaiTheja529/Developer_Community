"""/api/resources endpoints (spec §8.6)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common.content import get_or_404, is_mod
from app.common.errors import forbidden
from app.common.pagination import paginate
from app.common.ratelimit import creation_limit, enforce, limit
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import parse_body, validate_query
from app.extensions import db
from app.modules.resources import service
from app.modules.resources.models import Resource
from app.modules.resources.schemas import CheckUrlQuery, ResourceCreate, ResourceListQuery, ResourceUpdate

bp = Blueprint("resources", __name__, url_prefix="/api/resources")


@bp.get("")
@optional_auth
@validate_query(ResourceListQuery)
def list_resources(query: ResourceListQuery):
    page = paginate(service.list_resources(query, g.current_user), query.page, query.page_size)
    return paginated(service.summaries(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.get("/check-url")
@require_auth
@validate_query(CheckUrlQuery)
def check_url(query: CheckUrlQuery):
    return ok(service.check_url_info(query.url, g.current_user))


@bp.post("")
@require_auth
@require_verified
@limit(creation_limit, "create_resource")
def create_resource():
    body = parse_body(ResourceCreate)
    r = service.create(g.current_user, body)
    return created(service.detail(r, g.current_user))


@bp.get("/<uuid:resource_id>")
@optional_auth
def get_resource(resource_id: uuid.UUID):
    return ok(service.detail(get_or_404(Resource, resource_id, g.current_user), g.current_user))


@bp.patch("/<uuid:resource_id>")
@require_auth
@require_verified
def update_resource(resource_id: uuid.UUID):
    body = parse_body(ResourceUpdate)
    r = service.update_resource(service.get_for_owner(resource_id, g.current_user), body)
    return ok(service.detail(r, g.current_user))


@bp.delete("/<uuid:resource_id>")
@require_auth
@require_verified
def delete_resource(resource_id: uuid.UUID):
    service.soft_delete(resource_id, g.current_user)
    return no_content()


@bp.post("/<uuid:resource_id>/recheck")
@require_auth
@require_verified
def recheck(resource_id: uuid.UUID):
    r = get_or_404(Resource, resource_id, g.current_user)
    if r.submitter_id != g.current_user.id and not is_mod(g.current_user):
        raise forbidden()
    enforce("1 per 10 minutes", "resource_recheck", key=f"resource:{resource_id}")
    service.run_link_check(r)
    db.session.commit()
    return ok(service.detail(r, g.current_user))
