"""Shared content helpers: target registry, visibility (§5.8), viewer state (§5.7), user summaries."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, or_, select

from app.common.errors import not_found
from app.extensions import db

# Users -----------------------------------------------------------------------------------


def user_summary(user) -> dict | None:
    if user is None:
        return None
    deleted = user.status == "deleted"
    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_deleted": deleted,
    }


def load_users(ids: Iterable) -> dict:
    from app.modules.users.models import User

    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {u.id: u for u in db.session.execute(select(User).where(User.id.in_(ids))).scalars()}


# Categories -----------------------------------------------------------------------------


def category_by_slug(module: str, slug: str):
    from app.common.errors import validation_error
    from app.modules.meta.models import Category

    cat = db.session.execute(
        select(Category).where(Category.module == module, Category.slug == slug, Category.is_active.is_(True))
    ).scalar_one_or_none()
    if cat is None:
        raise validation_error({"category": f"Unknown category '{slug}'."})
    return cat


def categories_by_id(ids: Iterable[int]) -> dict:
    from app.modules.meta.models import Category

    ids = {i for i in ids if i is not None}
    if not ids:
        return {}
    return {c.id: c for c in db.session.execute(select(Category).where(Category.id.in_(ids))).scalars()}


def category_dict(cat) -> dict | None:
    return {"slug": cat.slug, "name": cat.name} if cat else None


# Visibility -----------------------------------------------------------------------------


def _status_attr(model) -> str:
    return getattr(model, "status_attr", "status")


def owner_id_of(obj) -> uuid.UUID | None:
    return getattr(obj, getattr(type(obj), "owner_attr", "author_id"), None)


def is_mod(viewer) -> bool:
    return viewer is not None and viewer.role in ("moderator", "admin")


def can_view(obj, viewer) -> bool:
    """Visibility of the row itself (not its parent)."""
    if obj is None or getattr(obj, "deleted_at", None) is not None:
        return False
    status = getattr(obj, _status_attr(type(obj)), "published")
    if status == "published":
        pass
    elif status == "hidden":
        if not (is_mod(viewer) or (viewer is not None and owner_id_of(obj) == viewer.id)):
            return False
    elif status == "removed":
        if not is_mod(viewer):
            return False
    # Private collections: owner only.
    if getattr(obj, "visibility", None) == "private" and not (viewer is not None and owner_id_of(obj) == viewer.id):
        return False
    return True


def public_clause(model):
    """Rows shown in public lists: not deleted and published."""
    return and_(model.deleted_at.is_(None), getattr(model, _status_attr(model)) == "published")


def viewer_list_clause(model, viewer, include_own_hidden: bool = False):
    """Public lists; optionally also the viewer's own hidden rows (e.g. their contributions page)."""
    base = public_clause(model)
    if viewer is not None and include_own_hidden:
        owner_col = getattr(model, model.owner_attr)
        return or_(
            base,
            and_(model.deleted_at.is_(None), owner_col == viewer.id, getattr(model, _status_attr(model)) == "hidden"),
        )
    return base


def get_or_404(model, row_id, viewer, lock: bool = False):
    stmt = select(model).where(model.id == row_id)
    if lock:
        stmt = stmt.with_for_update()
    obj = db.session.execute(stmt).scalar_one_or_none()
    if obj is None or not can_view(obj, viewer):
        raise not_found()
    return obj


# Target registry ------------------------------------------------------------------------


@dataclass
class TargetInfo:
    name: str
    plural: str

    @property
    def model(self):
        return _MODELS()[self.name]


TARGETS = {
    "harness": TargetInfo("harness", "harnesses"),
    "idea": TargetInfo("idea", "ideas"),
    "resource": TargetInfo("resource", "resources"),
    "collection": TargetInfo("collection", "collections"),
    "comment": TargetInfo("comment", "comments"),
    "suggestion": TargetInfo("suggestion", "suggestions"),
    "review": TargetInfo("review", "reviews"),
    "user": TargetInfo("user", "users"),
    "ai_message": TargetInfo("ai_message", "ai_messages"),
    "ai_draft": TargetInfo("ai_draft", "ai_drafts"),
}


def _MODELS() -> dict:  # noqa: N802 - lazy import table
    from app.modules.ai.models import AIDraft, AIMessage
    from app.modules.collections.models import Collection
    from app.modules.comments.models import Comment
    from app.modules.harnesses.models import Harness, HarnessReview
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource
    from app.modules.suggestions.models import Suggestion
    from app.modules.users.models import User

    return {
        "harness": Harness,
        "idea": Idea,
        "resource": Resource,
        "collection": Collection,
        "comment": Comment,
        "suggestion": Suggestion,
        "review": HarnessReview,
        "user": User,
        "ai_message": AIMessage,
        "ai_draft": AIDraft,
    }


def model_for(target_type: str):
    return _MODELS()[target_type]


def parent_of(target_type: str, obj) -> tuple[str, Any] | None:
    """For comments/suggestions/reviews: (parent_type, parent_id)."""
    if target_type in ("comment", "suggestion"):
        return obj.target
    if target_type == "review":
        return "harness", obj.harness_id
    return None


def load_target(target_type: str, target_id, viewer, lock: bool = False):
    """Load a community target and check it (and its parent) is visible to the viewer; 404 otherwise."""
    if target_type not in ("harness", "idea", "resource", "collection", "comment", "suggestion", "review"):
        raise not_found()
    obj = get_or_404(model_for(target_type), target_id, viewer, lock=lock)
    parent = parent_of(target_type, obj)
    if parent is not None:
        get_or_404(model_for(parent[0]), parent[1], viewer)
    return obj


def title_of(target_type: str, obj) -> str:
    if obj is None:
        return ""
    for attr in ("name", "title"):
        v = getattr(obj, attr, None)
        if v:
            return v
    if target_type == "comment":
        from app.common.text import snippet

        return snippet(obj.body, 60)
    if target_type == "review":
        return "Testing report"
    if target_type == "user":
        return obj.display_name
    return target_type


def url_path_of(target_type: str, obj) -> str:
    if obj is None:
        return "/"
    if target_type == "harness":
        return f"/harnesses/{obj.id}/{obj.slug}"
    if target_type == "idea":
        return f"/ideas/{obj.id}/{obj.slug}"
    if target_type == "resource":
        return f"/resources/{obj.id}"
    if target_type == "collection":
        return f"/collections/{obj.id}/{obj.slug}"
    if target_type == "user":
        return f"/u/{obj.username}"
    parent = parent_of(target_type, obj)
    if parent is not None:
        pobj = db.session.get(model_for(parent[0]), parent[1])
        anchor = {"comment": "comment", "suggestion": "suggestion", "review": "review"}[target_type]
        return f"{url_path_of(parent[0], pobj)}#{anchor}-{obj.id}"
    return "/"


# Viewer state ---------------------------------------------------------------------------

_EMPTY_VIEWER = {
    "is_owner": False,
    "has_voted": False,
    "has_interest": False,
    "has_bookmarked": False,
    "can_edit": False,
    "can_moderate": False,
}


def viewer_states(target_type: str, objs: list, viewer) -> dict:
    """One batched query each for votes and bookmarks (never one per row)."""
    from app.modules.votes.models import Bookmark, Vote

    if not objs:
        return {}
    if viewer is None:
        return {o.id: dict(_EMPTY_VIEWER) for o in objs}
    ids = [o.id for o in objs]
    votes = db.session.execute(
        select(Vote.target_id, Vote.kind).where(
            Vote.user_id == viewer.id, Vote.target_type == target_type, Vote.target_id.in_(ids)
        )
    ).all()
    voted = {(tid, kind) for tid, kind in votes}
    bookmarked: set = set()
    if target_type in ("harness", "idea", "resource", "collection"):
        bookmarked = set(
            db.session.execute(
                select(Bookmark.target_id).where(
                    Bookmark.user_id == viewer.id, Bookmark.target_type == target_type, Bookmark.target_id.in_(ids)
                )
            ).scalars()
        )
    mod = is_mod(viewer)
    out = {}
    for o in objs:
        owner = owner_id_of(o) == viewer.id
        out[o.id] = {
            "is_owner": owner,
            "has_voted": (o.id, "upvote") in voted,
            "has_interest": (o.id, "interest") in voted,
            "has_bookmarked": o.id in bookmarked,
            "can_edit": owner,
            "can_moderate": mod,
        }
    return out


def empty_viewer() -> dict:
    return dict(_EMPTY_VIEWER)
