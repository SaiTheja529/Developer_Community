"""Shared threaded comments for harnesses, ideas, resources and collections (spec §8.8)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select

from app.common.content import (
    can_view,
    get_or_404,
    is_mod,
    load_users,
    model_for,
    owner_id_of,
    user_summary,
    viewer_states,
)
from app.common.counters import bump
from app.common.errors import ApiError, bad_request, forbidden, not_found, validation_error
from app.extensions import db
from app.modules.comments.models import Comment
from app.modules.notifications.service import notify

EDIT_WINDOW = timedelta(days=7)
INLINE_REPLIES = 3


def _visible_clause(viewer):
    """Rows a viewer can read in full. Deleted/hidden rows may still appear as placeholders."""
    clause = and_(Comment.deleted_at.is_(None), Comment.status == "published")
    if viewer is not None:
        if is_mod(viewer):
            clause = or_(clause, and_(Comment.deleted_at.is_(None)))
        else:
            clause = or_(
                clause,
                and_(Comment.deleted_at.is_(None), Comment.status == "hidden", Comment.author_id == viewer.id),
            )
    return clause


def _placeholder_ok():
    """Top-level rows that are deleted/hidden but have replies are returned as placeholders."""
    return Comment.reply_count > 0


def serialize(comments: list[Comment], viewer, replies_by_parent: dict | None = None) -> list[dict]:
    visible_ids = {c.id for c in comments if can_view(c, viewer)}
    users = load_users(c.author_id for c in comments if c.id in visible_ids)
    states = viewer_states("comment", [c for c in comments if c.id in visible_ids], viewer)
    out = []
    for c in comments:
        if c.id not in visible_ids:
            item = {
                "id": str(c.id),
                "deleted": True,
                "body": None,
                "author": None,
                "parent_id": str(c.parent_id) if c.parent_id else None,
                "reply_count": c.reply_count,
                "created_at": c.created_at,
            }
        else:
            item = {
                "id": str(c.id),
                "deleted": False,
                "parent_id": str(c.parent_id) if c.parent_id else None,
                "author": user_summary(users.get(c.author_id)),
                "body": c.body,
                "ai_assisted": c.ai_assisted,
                "counts": {"votes": c.vote_count, "replies": c.reply_count},
                "reply_count": c.reply_count,
                "status": c.status,
                "edited_at": c.edited_at,
                "created_at": c.created_at,
                "updated_at": c.updated_at,
                "viewer": states[c.id],
            }
        if replies_by_parent is not None and c.parent_id is None:
            item["replies"] = serialize(replies_by_parent.get(c.id, []), viewer)
        out.append(item)
    return out


def top_level_stmt(target_type: str, target_id, viewer, sort: str):
    col = getattr(Comment, f"{target_type}_id")
    stmt = select(Comment).where(
        col == target_id, Comment.parent_id.is_(None), or_(_visible_clause(viewer), _placeholder_ok())
    )
    if sort == "newest":
        return stmt.order_by(Comment.created_at.desc())
    if sort == "top":
        return stmt.order_by(Comment.vote_count.desc(), Comment.created_at.asc())
    if sort == "oldest":
        return stmt.order_by(Comment.created_at.asc())
    raise bad_request(f"Unknown sort '{sort}'.")


def inline_replies(parent_ids: list, viewer) -> dict:
    if not parent_ids:
        return {}
    rn = func.row_number().over(partition_by=Comment.parent_id, order_by=Comment.created_at.asc()).label("rn")
    sub = (
        select(Comment.id, rn)
        .where(Comment.parent_id.in_(parent_ids), _visible_clause(viewer))
        .subquery()
    )
    rows = db.session.execute(
        select(Comment).join(sub, sub.c.id == Comment.id).where(sub.c.rn <= INLINE_REPLIES).order_by(Comment.created_at)
    ).scalars().all()
    out: dict = {}
    for r in rows:
        out.setdefault(r.parent_id, []).append(r)
    return out


def replies_stmt(parent_id, viewer):
    return (
        select(Comment)
        .where(Comment.parent_id == parent_id, _visible_clause(viewer))
        .order_by(Comment.created_at.asc())
    )


def create(target_type: str, target_id, user, body) -> Comment:
    model = model_for(target_type)
    target = get_or_404(model, target_id, user)
    parent = None
    if body.parent_id is not None:
        parent = db.session.get(Comment, body.parent_id)
        if parent is None or getattr(parent, f"{target_type}_id") != target.id:
            raise validation_error({"parent_id": "Parent comment not found on this item."})
        if parent.parent_id is not None:  # reply to a reply attaches to the top-level parent
            parent = db.session.get(Comment, parent.parent_id)
        if parent.deleted_at is not None:
            raise validation_error({"parent_id": "You cannot reply to a deleted comment."})
    c = Comment(
        author_id=user.id,
        parent_id=parent.id if parent else None,
        body=body.body,
        ai_assisted=body.ai_assisted,
        **{f"{target_type}_id": target.id},
    )
    db.session.add(c)
    db.session.flush()
    bump(model, target.id, "comment_count", 1, touch_activity=True)
    if parent is not None:
        bump(Comment, parent.id, "reply_count", 1)
        notify(parent.author_id, user, "reply_to_comment", target_type, target, snippet_text=body.body)
    else:
        notify(owner_id_of(target), user, "comment_on_content", target_type, target, snippet_text=body.body)
    db.session.commit()
    return c


def get_comment(comment_id, viewer) -> Comment:
    c = db.session.get(Comment, comment_id)
    if c is None or not can_view(c, viewer):
        raise not_found()
    ttype, tid = c.target
    get_or_404(model_for(ttype), tid, viewer)
    return c


def get_comment_for_replies(comment_id, viewer) -> Comment:
    """Replies stay readable under a deleted parent (thread placeholders), as long as the target is visible."""
    c = db.session.get(Comment, comment_id)
    if c is None:
        raise not_found()
    ttype, tid = c.target
    get_or_404(model_for(ttype), tid, viewer)
    return c


def update(comment_id, user, body) -> Comment:
    c = get_comment(comment_id, user)
    if c.author_id != user.id:
        raise forbidden("Only the author can edit this comment.")
    if datetime.now(UTC) - c.created_at > EDIT_WINDOW:
        raise ApiError("forbidden", "Comments can only be edited for 7 days after posting.", 403)
    c.body = body.body
    c.edited_at = datetime.now(UTC)
    if body.ai_assisted:
        c.ai_assisted = True
    db.session.commit()
    return c


def delete(comment_id, user) -> None:
    c = get_comment(comment_id, user)
    ttype, tid = c.target
    target = db.session.get(model_for(ttype), tid)
    if not (c.author_id == user.id or owner_id_of(target) == user.id or is_mod(user)):
        raise forbidden()
    c.deleted_at = datetime.now(UTC)
    bump(model_for(ttype), tid, "comment_count", -1)
    if c.parent_id is not None:
        bump(Comment, c.parent_id, "reply_count", -1)
    db.session.commit()
