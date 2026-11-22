"""Idempotent votes and bookmarks with atomic counters (spec §8.10)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.common.content import load_target, model_for, owner_id_of
from app.common.counters import bump
from app.common.errors import bad_request, forbidden, not_found
from app.extensions import db
from app.modules.votes.models import Bookmark, Vote

VOTE_TARGETS = ("harness", "idea", "resource", "collection", "comment", "suggestion", "review")
BOOKMARK_TARGETS = ("harness", "idea", "resource", "collection")


def _counter_field(kind: str) -> str:
    return "interest_count" if kind == "interest" else "vote_count"


def _validate_vote(target_type: str, kind: str) -> None:
    if target_type not in VOTE_TARGETS:
        raise not_found()
    if kind not in ("upvote", "interest"):
        raise bad_request("kind must be 'upvote' or 'interest'.")
    if kind == "interest" and target_type != "idea":
        raise bad_request("'interest' is only valid for ideas.")


def _count(target_type: str, target_id, field: str) -> int:
    model = model_for(target_type)
    return db.session.execute(select(getattr(model, field)).where(model.id == target_id)).scalar_one()


def set_vote(user, target_type: str, target_id, kind: str, active: bool) -> dict:
    _validate_vote(target_type, kind)
    target = load_target(target_type, target_id, user)
    if owner_id_of(target) == user.id:
        raise forbidden("You cannot vote on your own content.")
    model = model_for(target_type)
    field = _counter_field(kind)
    if active:
        res = db.session.execute(
            insert(Vote)
            .values(user_id=user.id, target_type=target_type, target_id=target.id, kind=kind)
            .on_conflict_do_nothing()
            .returning(Vote.user_id)
        )
        if res.first() is not None:  # a row was actually inserted
            bump(model, target.id, field, 1)
    else:
        res = db.session.execute(
            delete(Vote).where(
                Vote.user_id == user.id, Vote.target_type == target_type, Vote.target_id == target.id, Vote.kind == kind
            )
        )
        if res.rowcount:
            bump(model, target.id, field, -1)
    db.session.commit()
    return {"count": _count(target_type, target.id, field), "active": active, "kind": kind}


def set_bookmark(user, target_type: str, target_id, active: bool) -> dict:
    if target_type not in BOOKMARK_TARGETS:
        raise not_found()
    model = model_for(target_type)
    if active:
        target = load_target(target_type, target_id, user)
        res = db.session.execute(
            insert(Bookmark)
            .values(user_id=user.id, target_type=target_type, target_id=target.id)
            .on_conflict_do_nothing()
            .returning(Bookmark.user_id)
        )
        if res.first() is not None:
            bump(model, target.id, "bookmark_count", 1)
    else:
        # Allow removing bookmarks even if the target was hidden/deleted meanwhile.
        res = db.session.execute(
            delete(Bookmark).where(
                Bookmark.user_id == user.id, Bookmark.target_type == target_type, Bookmark.target_id == target_id
            )
        )
        if res.rowcount:
            bump(model, target_id, "bookmark_count", -1)
    db.session.commit()
    count = db.session.execute(select(model.bookmark_count).where(model.id == target_id)).scalar_one_or_none() or 0
    return {"count": count, "active": active}


# Summaries by type (used by bookmarks list and contributions) ------------------------------


def serialize_summaries(target_type: str, objs: list, viewer) -> list[dict]:
    if target_type == "harness":
        from app.modules.harnesses.service import summaries
    elif target_type == "idea":
        from app.modules.ideas.service import summaries
    elif target_type == "resource":
        from app.modules.resources.service import summaries
    elif target_type == "collection":
        from app.modules.collections.service import summaries
    else:  # pragma: no cover
        raise ValueError(target_type)
    return summaries(objs, viewer)


def summaries_for(target_type: str, ids: list, viewer) -> list[dict]:
    from app.common.content import can_view

    model = model_for(target_type)
    objs = [o for o in db.session.execute(select(model).where(model.id.in_(ids))).scalars() if can_view(o, viewer)]
    return serialize_summaries(target_type, objs, viewer)
