from __future__ import annotations

import uuid

from flask import Blueprint, g
from sqlalchemy import select

from app.auth.decorators import require_auth
from app.common.errors import not_found
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import limit
from app.common.responses import ok, paginated
from app.common.validation import QueryBool, validate_query
from app.extensions import db
from app.modules.notifications import service
from app.modules.notifications.models import Notification

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


class NotificationQuery(PageParams):
    unread_only: QueryBool = False


@bp.get("")
@require_auth
@validate_query(NotificationQuery)
def list_notifications(query: NotificationQuery):
    stmt = select(Notification).where(Notification.recipient_id == g.current_user.id)
    if query.unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)
    return paginated(service.serialize(page.items), page.page, page.page_size, page.total)


@bp.get("/unread-count")
@require_auth
@limit("60 per minute", "notifications_unread")
def unread_count():
    return ok({"count": service.unread_count(g.current_user.id)})


@bp.post("/<uuid:notification_id>/read")
@require_auth
def mark_read(notification_id: uuid.UUID):
    n = db.session.get(Notification, notification_id)
    if n is None or n.recipient_id != g.current_user.id:
        raise not_found()
    service.mark_read(g.current_user.id, notification_id)
    db.session.commit()
    return ok({"id": str(notification_id), "read": True})


@bp.post("/read-all")
@require_auth
def read_all():
    count = service.mark_all_read(g.current_user.id)
    db.session.commit()
    return ok({"updated": count})
