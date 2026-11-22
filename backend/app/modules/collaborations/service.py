"""Collaboration requests for ideas and harnesses, with the contact-reveal rule (spec §8.5)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.common.content import get_or_404, load_users, model_for, title_of, url_path_of, user_summary
from app.common.counters import bump
from app.common.errors import ApiError, conflict, forbidden, not_found
from app.extensions import db
from app.modules.collaborations.models import CollaborationRequest
from app.modules.notifications.service import notify


def _target_col(target_type: str):
    return CollaborationRequest.idea_id if target_type == "idea" else CollaborationRequest.harness_id


def viewer_request(target_type: str, target_id, viewer) -> dict | None:
    if viewer is None:
        return None
    row = db.session.execute(
        select(CollaborationRequest)
        .where(
            _target_col(target_type) == target_id,
            CollaborationRequest.requester_id == viewer.id,
            CollaborationRequest.status.in_(("pending", "accepted")),
        )
        .order_by(CollaborationRequest.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return {"id": str(row.id), "status": row.status} if row else None


def pending_count(target_type: str, target_id) -> int:
    return db.session.execute(
        select(func.count()).where(_target_col(target_type) == target_id, CollaborationRequest.status == "pending")
    ).scalar_one()


def withdraw_pending_for_target(target_type: str, target_id) -> None:
    db.session.execute(
        update(CollaborationRequest)
        .where(_target_col(target_type) == target_id, CollaborationRequest.status == "pending")
        .values(status="withdrawn", updated_at=func.now())
    )


def _contact_for(user) -> dict:
    links = (user.contact_links or []) if user.contact_visibility != "hidden" else []
    return {"email": user.email, "links": links}


def serialize(requests: list[CollaborationRequest], viewer) -> list[dict]:
    users = load_users([r.requester_id for r in requests] + [r.owner_id for r in requests])
    out = []
    for r in requests:
        ttype, tid = r.target
        target = db.session.get(model_for(ttype), tid)
        requester, owner = users.get(r.requester_id), users.get(r.owner_id)
        counterpart_contact = None
        if r.status == "accepted" and viewer is not None:
            if viewer.id == r.owner_id and r.requester_shares_contact and requester and requester.status != "deleted":
                counterpart_contact = _contact_for(requester)
            elif viewer.id == r.requester_id and r.owner_shares_contact and owner and owner.status != "deleted":
                counterpart_contact = _contact_for(owner)
        out.append(
            {
                "id": str(r.id),
                "target": {
                    "type": ttype,
                    "id": str(tid),
                    "title": title_of(ttype, target),
                    "url_path": url_path_of(ttype, target),
                },
                "requester": user_summary(requester),
                "owner": user_summary(owner),
                "message": r.message,
                "skills": r.skills,
                "status": r.status,
                "response_message": r.response_message,
                "created_at": r.created_at,
                "responded_at": r.responded_at,
                "counterpart_contact": counterpart_contact,
                "viewer_role": "owner" if viewer and viewer.id == r.owner_id else "requester",
            }
        )
    return out


def create(target_type: str, target_id, user, body) -> CollaborationRequest:
    target = get_or_404(model_for(target_type), target_id, user, lock=True)
    if target.author_id == user.id:
        raise forbidden("You cannot request to collaborate on your own content.")
    if target_type == "idea" and target.collaboration_status != "seeking_collaborators":
        raise conflict("This idea is not looking for collaborators right now.")
    if target_type == "harness" and not target.accepts_collaboration:
        raise conflict("This harness is not accepting collaboration requests.")
    accepted = db.session.execute(
        select(CollaborationRequest.id).where(
            _target_col(target_type) == target.id,
            CollaborationRequest.requester_id == user.id,
            CollaborationRequest.status == "accepted",
        )
    ).first()
    if accepted:
        raise conflict("You are already a collaborator.")
    req = CollaborationRequest(
        requester_id=user.id,
        owner_id=target.author_id,
        message=body.message,
        skills=body.skills,
        requester_shares_contact=body.share_contact,
        **{f"{target_type}_id": target.id},
    )
    db.session.add(req)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("conflict", "You already have a pending request for this.", 409) from e
    notify(target.author_id, user, "collab_request_received", target_type, target, snippet_text=body.message)
    db.session.commit()
    return req


def get_visible(request_id, user, lock: bool = False) -> CollaborationRequest:
    stmt = select(CollaborationRequest).where(CollaborationRequest.id == request_id)
    if lock:
        stmt = stmt.with_for_update()
    r = db.session.execute(stmt).scalar_one_or_none()
    if r is None or user.id not in (r.requester_id, r.owner_id):
        raise not_found()
    return r


def respond(request_id, user, accept: bool, body) -> CollaborationRequest:
    r = get_visible(request_id, user, lock=True)
    if r.owner_id != user.id:
        raise forbidden("Only the owner can respond to this request.")
    if r.status != "pending":
        raise conflict(f"This request is already {r.status}.")
    r.status = "accepted" if accept else "declined"
    r.response_message = body.message
    r.responded_at = datetime.now(UTC)
    if accept:
        r.owner_shares_contact = bool(getattr(body, "share_contact", False))
        if r.idea_id is not None:
            from app.modules.ideas.models import Idea

            bump(Idea, r.idea_id, "collaborator_count", 1)
    ttype, tid = r.target
    target = db.session.get(model_for(ttype), tid)
    notify(
        r.requester_id,
        user,
        "collab_request_accepted" if accept else "collab_request_declined",
        ttype,
        target,
        snippet_text=body.message,
    )
    db.session.commit()
    return r


def withdraw(request_id, user) -> CollaborationRequest:
    r = get_visible(request_id, user, lock=True)
    if r.requester_id != user.id:
        raise forbidden("Only the requester can withdraw this request.")
    if r.status != "pending":
        raise conflict(f"This request is already {r.status}.")
    r.status = "withdrawn"
    db.session.commit()
    return r
