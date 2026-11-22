"""In-app notifications with batching (spec §14)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select, update

from app.common.content import load_users, title_of, url_path_of, user_summary
from app.common.text import snippet
from app.extensions import db
from app.modules.notifications.models import Notification


def notify(
    recipient_id,
    actor,
    ntype: str,
    target_type: str,
    target_obj,
    *,
    snippet_text: str | None = None,
    title_obj=None,
    title_type: str | None = None,
) -> None:
    """Create (or batch into) a notification. Never notifies the actor about their own action.

    `target_obj` is what the notification points at (e.g. the harness). `title_obj` defaults to it.
    """
    if recipient_id is None:
        return
    if actor is not None and recipient_id == actor.id:
        return
    tobj = title_obj if title_obj is not None else target_obj
    ttype = title_type or target_type
    data = {
        "target_title": title_of(ttype, tobj),
        "url_path": url_path_of(target_type, target_obj),
        "snippet": snippet(snippet_text, 140) if snippet_text else "",
        "actor_display_name": actor.display_name if actor is not None else None,
        "count": 1,
    }
    existing = db.session.execute(
        select(Notification)
        .where(
            Notification.recipient_id == recipient_id,
            Notification.type == ntype,
            Notification.target_type == target_type,
            Notification.target_id == target_obj.id,
            Notification.read_at.is_(None),
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        merged = dict(existing.data or {})
        merged["count"] = int(merged.get("count", 1)) + 1
        merged["actor_display_name"] = data["actor_display_name"]
        merged["snippet"] = data["snippet"] or merged.get("snippet", "")
        existing.data = merged
        existing.actor_id = actor.id if actor is not None else None
        existing.created_at = datetime.now(UTC)
        return
    db.session.add(
        Notification(
            recipient_id=recipient_id,
            actor_id=actor.id if actor is not None else None,
            type=ntype,
            target_type=target_type,
            target_id=target_obj.id,
            data=data,
        )
    )


def serialize(notifications: list[Notification]) -> list[dict]:
    actors = load_users(n.actor_id for n in notifications)
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "target_type": n.target_type,
            "target_id": str(n.target_id),
            "data": n.data,
            "actor": user_summary(actors.get(n.actor_id)),
            "read": n.read_at is not None,
            "read_at": n.read_at,
            "created_at": n.created_at,
        }
        for n in notifications
    ]


def unread_count(user_id) -> int:
    return db.session.execute(
        select(func.count()).select_from(Notification).where(
            Notification.recipient_id == user_id, Notification.read_at.is_(None)
        )
    ).scalar_one()


def mark_read(user_id, notification_id) -> bool:
    res = db.session.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.recipient_id == user_id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    return bool(res.rowcount)


def mark_all_read(user_id) -> int:
    res = db.session.execute(
        update(Notification)
        .where(Notification.recipient_id == user_id, Notification.read_at.is_(None))
        .values(read_at=func.now())
    )
    return res.rowcount or 0
