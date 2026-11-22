"""Collaboration request endpoints (spec §8.5)."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, g
from pydantic import Field
from sqlalchemy import select

from app.auth.decorators import require_auth, require_verified
from app.common.content import get_or_404, model_for
from app.common.errors import forbidden
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import limit
from app.common.responses import created, ok, paginated
from app.common.validation import OptText, StrictModel, Tags, Text, parse_body, validate_query
from app.modules.collaborations import service
from app.modules.collaborations.models import CollaborationRequest

bp = Blueprint("collaborations", __name__, url_prefix="/api")


class CollabCreate(StrictModel):
    message: Text(20, 2000)
    skills: Tags(10) = Field(default_factory=list)
    share_contact: bool = False


class AcceptBody(StrictModel):
    message: OptText(1000) = None
    share_contact: bool = False


class DeclineBody(StrictModel):
    message: OptText(1000) = None


class TargetRequestsQuery(PageParams):
    status: Literal["pending", "accepted", "declined", "withdrawn"] | None = None


class InboxQuery(PageParams):
    role: Literal["sent", "received"] = "received"
    status: Literal["pending", "accepted", "declined", "withdrawn"] | None = None


def _create(target_type: str, target_id):
    body = parse_body(CollabCreate)
    req = service.create(target_type, target_id, g.current_user, body)
    return created(service.serialize([req], g.current_user)[0])


def _list_for_target(target_type: str, target_id, query: TargetRequestsQuery):
    target = get_or_404(model_for(target_type), target_id, g.current_user)
    if target.author_id != g.current_user.id and g.current_user.role != "admin":
        raise forbidden("Only the owner can view requests.")
    col = CollaborationRequest.idea_id if target_type == "idea" else CollaborationRequest.harness_id
    stmt = select(CollaborationRequest).where(col == target.id)
    if query.status:
        stmt = stmt.where(CollaborationRequest.status == query.status)
    stmt = stmt.order_by(CollaborationRequest.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)
    return paginated(service.serialize(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.post("/ideas/<uuid:target_id>/collaboration-requests")
@require_auth
@require_verified
@limit("10 per day", "collab_request")
def create_idea_request(target_id: uuid.UUID):
    return _create("idea", target_id)


@bp.post("/harnesses/<uuid:target_id>/collaboration-requests")
@require_auth
@require_verified
@limit("10 per day", "collab_request")
def create_harness_request(target_id: uuid.UUID):
    return _create("harness", target_id)


@bp.get("/ideas/<uuid:target_id>/collaboration-requests")
@require_auth
@validate_query(TargetRequestsQuery)
def list_idea_requests(target_id: uuid.UUID, query: TargetRequestsQuery):
    return _list_for_target("idea", target_id, query)


@bp.get("/harnesses/<uuid:target_id>/collaboration-requests")
@require_auth
@validate_query(TargetRequestsQuery)
def list_harness_requests(target_id: uuid.UUID, query: TargetRequestsQuery):
    return _list_for_target("harness", target_id, query)


@bp.get("/collaborations")
@require_auth
@validate_query(InboxQuery)
def inbox(query: InboxQuery):
    col = CollaborationRequest.requester_id if query.role == "sent" else CollaborationRequest.owner_id
    stmt = select(CollaborationRequest).where(col == g.current_user.id)
    if query.status:
        stmt = stmt.where(CollaborationRequest.status == query.status)
    stmt = stmt.order_by(CollaborationRequest.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)
    return paginated(service.serialize(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.get("/collaborations/<uuid:request_id>")
@require_auth
def get_request(request_id: uuid.UUID):
    return ok(service.serialize([service.get_visible(request_id, g.current_user)], g.current_user)[0])


@bp.post("/collaborations/<uuid:request_id>/accept")
@require_auth
@require_verified
def accept(request_id: uuid.UUID):
    body = parse_body(AcceptBody, allow_empty=True)
    r = service.respond(request_id, g.current_user, True, body)
    return ok(service.serialize([r], g.current_user)[0])


@bp.post("/collaborations/<uuid:request_id>/decline")
@require_auth
@require_verified
def decline(request_id: uuid.UUID):
    body = parse_body(DeclineBody, allow_empty=True)
    r = service.respond(request_id, g.current_user, False, body)
    return ok(service.serialize([r], g.current_user)[0])


@bp.post("/collaborations/<uuid:request_id>/withdraw")
@require_auth
def withdraw(request_id: uuid.UUID):
    r = service.withdraw(request_id, g.current_user)
    return ok(service.serialize([r], g.current_user)[0])


