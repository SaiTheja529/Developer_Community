"""PUT/DELETE /api/votes/... and /api/bookmarks/... (spec §8.10)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g, request

from app.auth.decorators import require_auth, require_verified
from app.common.responses import ok
from app.modules.votes import service

bp = Blueprint("votes", __name__, url_prefix="/api")


@bp.put("/votes/<string:target_type>/<uuid:target_id>")
@require_auth
@require_verified
def put_vote(target_type: str, target_id: uuid.UUID):
    kind = request.args.get("kind", "upvote")
    return ok(service.set_vote(g.current_user, target_type, target_id, kind, True))


@bp.delete("/votes/<string:target_type>/<uuid:target_id>")
@require_auth
@require_verified
def delete_vote(target_type: str, target_id: uuid.UUID):
    kind = request.args.get("kind", "upvote")
    return ok(service.set_vote(g.current_user, target_type, target_id, kind, False))


@bp.put("/bookmarks/<string:target_type>/<uuid:target_id>")
@require_auth
@require_verified
def put_bookmark(target_type: str, target_id: uuid.UUID):
    return ok(service.set_bookmark(g.current_user, target_type, target_id, True))


@bp.delete("/bookmarks/<string:target_type>/<uuid:target_id>")
@require_auth
@require_verified
def delete_bookmark(target_type: str, target_id: uuid.UUID):
    return ok(service.set_bookmark(g.current_user, target_type, target_id, False))
