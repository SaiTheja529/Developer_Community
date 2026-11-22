"""/api/users/* endpoints (spec §6.6 account management, §8.2 profiles)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g, make_response
from sqlalchemy import select

from app.auth import service as auth_service
from app.auth import sessions
from app.auth.decorators import optional_auth, require_auth
from app.auth.schemas import ChangeEmailBody, ChangePasswordBody, DeleteAccountBody
from app.common.content import can_view, viewer_list_clause
from app.common.errors import not_found
from app.common.pagination import paginate
from app.common.responses import accepted, ok, paginated
from app.common.validation import parse_body, validate_query
from app.extensions import db
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import (
    BookmarksQuery,
    CheckUsernameQuery,
    ContributionsQuery,
    MyCollectionsQuery,
    UpdateMeBody,
)

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.get("/me")
@require_auth
def get_me():
    return ok(service.me_profile(g.current_user))


@bp.patch("/me")
@require_auth
def patch_me():
    body = parse_body(UpdateMeBody)
    user = service.update_me(g.current_user, body)
    return ok(service.me_profile(user))


@bp.delete("/me")
@require_auth
def delete_me():
    body = parse_body(DeleteAccountBody)
    auth_service.delete_account(g.current_user, body.password)
    resp = make_response("", 204)
    sessions.clear_refresh_cookie(resp)
    return resp


@bp.post("/me/password")
@require_auth
def change_password():
    body = parse_body(ChangePasswordBody)
    auth_service.change_password(g.current_user, g.session_id, body.current_password, body.new_password)
    from app.auth.models import AuthSession

    sess = db.session.get(AuthSession, g.session_id)
    return auth_service.token_response(g.current_user, sess, None)


@bp.post("/me/email")
@require_auth
def change_email():
    body = parse_body(ChangeEmailBody)
    auth_service.change_email(g.current_user, str(body.new_email), body.password)
    return accepted({"sent": True})


@bp.get("/check-username")
@validate_query(CheckUsernameQuery)
def check_username(query: CheckUsernameQuery):
    problem = service.username_problem(query.username.strip().lower())
    data = {"available": problem is None}
    if problem:
        data["reason"] = problem
    return ok(data)


@bp.get("/me/bookmarks")
@require_auth
@validate_query(BookmarksQuery)
def my_bookmarks(query: BookmarksQuery):
    from app.modules.votes.models import Bookmark
    from app.modules.votes.service import summaries_for

    stmt = select(Bookmark).where(Bookmark.user_id == g.current_user.id)
    if query.type:
        stmt = stmt.where(Bookmark.target_type == query.type)
    stmt = stmt.order_by(Bookmark.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)
    by_type: dict[str, list] = {}
    for bm in page.items:
        by_type.setdefault(bm.target_type, []).append(bm.target_id)
    resolved: dict = {}
    for ttype, ids in by_type.items():
        for item in summaries_for(ttype, ids, g.current_user):
            resolved[(ttype, item["id"])] = item
    items = []
    for bm in page.items:
        summary = resolved.get((bm.target_type, str(bm.target_id)))
        items.append(
            {
                "target_type": bm.target_type,
                "target_id": str(bm.target_id),
                "bookmarked_at": bm.created_at,
                "item": summary,
                "unavailable": summary is None,
            }
        )
    return paginated(items, page.page, page.page_size, page.total)


@bp.get("/me/collections")
@require_auth
@validate_query(MyCollectionsQuery)
def my_collections(query: MyCollectionsQuery):
    from app.modules.collections.models import Collection, CollectionItem

    rows = (
        db.session.execute(
            select(Collection)
            .where(Collection.owner_id == g.current_user.id, Collection.deleted_at.is_(None))
            .order_by(Collection.updated_at.desc())
        )
        .scalars()
        .all()
    )
    contains: set = set()
    if query.resource_id:
        try:
            rid = uuid.UUID(query.resource_id)
        except ValueError:
            rid = None
        if rid is not None and rows:
            contains = set(
                db.session.execute(
                    select(CollectionItem.collection_id).where(
                        CollectionItem.resource_id == rid, CollectionItem.collection_id.in_([c.id for c in rows])
                    )
                ).scalars()
            )
    return ok(
        [
            {
                "id": str(c.id),
                "slug": c.slug,
                "title": c.title,
                "visibility": c.visibility,
                "item_count": c.item_count,
                "status": c.status,
                "contains_resource": c.id in contains,
                "updated_at": c.updated_at,
            }
            for c in rows
        ]
    )


def _get_user_or_404(username: str) -> User:
    user = db.session.execute(select(User).where(User.username == username.lower())).scalar_one_or_none()
    if user is None or user.status == "deleted":
        raise not_found("User not found.")
    return user


@bp.get("/<string:username>")
@optional_auth
def public_profile(username: str):
    return ok(service.public_profile(_get_user_or_404(username)))


@bp.get("/<string:username>/contributions")
@optional_auth
@validate_query(ContributionsQuery)
def contributions(username: str, query: ContributionsQuery):
    from app.modules.collections.models import Collection
    from app.modules.harnesses.models import Harness, HarnessReview
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource

    user = _get_user_or_404(username)
    viewer = g.current_user
    own = viewer is not None and viewer.id == user.id
    model, owner_col = {
        "harnesses": (Harness, Harness.author_id),
        "ideas": (Idea, Idea.author_id),
        "resources": (Resource, Resource.submitter_id),
        "collections": (Collection, Collection.owner_id),
        "reviews": (HarnessReview, HarnessReview.author_id),
    }[query.type]
    stmt = select(model).where(owner_col == user.id, viewer_list_clause(model, viewer, include_own_hidden=own))
    if model is Collection and not own:
        stmt = stmt.where(Collection.visibility == "public")
    stmt = stmt.order_by(model.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)

    if query.type == "reviews":
        from app.modules.harnesses.service import review_dicts

        harness_ids = {r.harness_id for r in page.items}
        visible_harnesses = {
            h.id: h
            for h in db.session.execute(select(Harness).where(Harness.id.in_(harness_ids))).scalars()
            if can_view(h, viewer)
        }
        reviews = [r for r in page.items if r.harness_id in visible_harnesses]
        items = review_dicts(reviews, viewer)
        for item, r in zip(items, reviews, strict=True):
            h = visible_harnesses[r.harness_id]
            item["harness"] = {"id": str(h.id), "slug": h.slug, "name": h.name}
    else:
        from app.modules.votes.service import serialize_summaries

        singular = {"harnesses": "harness", "ideas": "idea", "resources": "resource", "collections": "collection"}
        items = serialize_summaries(singular[query.type], page.items, viewer)
    return paginated(items, page.page, page.page_size, page.total)
