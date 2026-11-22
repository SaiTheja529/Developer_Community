"""Suggestion routes. `make_suggestion_routes(target_type)` mounts per-target endpoints (spec §8.9)."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, g
from pydantic import field_validator

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common import enums
from app.common.content import TARGETS, get_or_404, model_for
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import limit
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import OptText, StrictModel, Text, parse_body, validate_query
from app.modules.suggestions import service


class SuggestionCreate(StrictModel):
    kind: str
    title: Text(5, 150)
    body: Text(10, 10000)
    payload: dict | None = None
    ai_assisted: bool = False


class SuggestionUpdate(StrictModel):
    title: Text(5, 150) | None = None
    body: Text(10, 10000) | None = None
    payload: dict | None = None
    ai_assisted: bool | None = None
    status: Literal[tuple(enums.SUGGESTION_STATUSES)] | None = None  # type: ignore[valid-type]
    owner_response: OptText(2000) = None

    @field_validator("title", "body", "status")
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class SuggestionListQuery(PageParams):
    kind: str | None = None
    status: str | None = None
    sort: Literal["top", "recent"] = "top"


def make_suggestion_routes(target_type: str) -> Blueprint:
    plural = TARGETS[target_type].plural
    bp = Blueprint(f"{target_type}_suggestions", __name__, url_prefix=f"/api/{plural}")

    @bp.get("/<uuid:target_id>/suggestions")
    @optional_auth
    @validate_query(SuggestionListQuery)
    def list_suggestions(target_id: uuid.UUID, query: SuggestionListQuery):
        get_or_404(model_for(target_type), target_id, g.current_user)
        stmt = service.list_stmt(target_type, target_id, g.current_user, query.kind, query.status, query.sort)
        page = paginate(stmt, query.page, query.page_size)
        return paginated(service.serialize(page.items, g.current_user), page.page, page.page_size, page.total)

    @bp.post("/<uuid:target_id>/suggestions")
    @require_auth
    @require_verified
    @limit("20 per hour", "create_suggestion")
    def create_suggestion(target_id: uuid.UUID):
        body = parse_body(SuggestionCreate)
        s = service.create(target_type, target_id, g.current_user, body)
        return created(service.serialize([s], g.current_user)[0])

    return bp


bp = Blueprint("suggestions", __name__, url_prefix="/api/suggestions")


@bp.patch("/<uuid:suggestion_id>")
@require_auth
@require_verified
def update_suggestion(suggestion_id: uuid.UUID):
    body = parse_body(SuggestionUpdate)
    s = service.update(suggestion_id, g.current_user, body)
    return ok(service.serialize([s], g.current_user)[0])


@bp.delete("/<uuid:suggestion_id>")
@require_auth
@require_verified
def delete_suggestion(suggestion_id: uuid.UUID):
    service.delete(suggestion_id, g.current_user)
    return no_content()
