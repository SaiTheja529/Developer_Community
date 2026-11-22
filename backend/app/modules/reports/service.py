"""Reports, moderation actions and auto-hide (spec §7.10, §8.10, §8.13)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.common.content import (
    load_target,
    load_users,
    model_for,
    owner_id_of,
    title_of,
    url_path_of,
    user_summary,
)
from app.common.counters import bump
from app.common.errors import ApiError, bad_request, not_found
from app.common.text import snippet
from app.extensions import db
from app.modules.notifications.service import notify
from app.modules.reports.models import ModerationAction, Report

SYSTEM_USERNAME = "devcommons"
AUTO_HIDE_THRESHOLD = 3
MODERATABLE = ("harness", "idea", "resource", "collection", "comment", "suggestion", "review")
FEATURABLE = ("harness", "idea", "resource", "collection")


def get_system_user():
    from app.modules.users.models import User

    return db.session.execute(select(User).where(User.username == SYSTEM_USERNAME)).scalar_one_or_none()


def log_action(actor_id, action: str, target_type: str, target_id, reason: str | None = None, metadata: dict | None = None):
    db.session.add(
        ModerationAction(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
            metadata_=metadata or {},
        )
    )


def _status_attr(target_type: str) -> str:
    return "moderation_status" if target_type == "suggestion" else "status"


# Reports ---------------------------------------------------------------------------------


def _check_report_target(user, target_type: str, target_id):
    from app.modules.ai.models import AIConversation, AIDraft, AIMessage
    from app.modules.users.models import User

    if target_type == "user":
        u = db.session.get(User, target_id)
        if u is None or u.status == "deleted":
            raise not_found()
        return u
    if target_type == "ai_message":
        msg = db.session.get(AIMessage, target_id)
        conv = db.session.get(AIConversation, msg.conversation_id) if msg else None
        if msg is None or conv is None or conv.user_id != user.id:
            raise not_found()
        return msg
    if target_type == "ai_draft":
        d = db.session.get(AIDraft, target_id)
        if d is None or d.user_id != user.id:
            raise not_found()
        return d
    return load_target(target_type, target_id, user)


def create_report(user, body) -> Report:
    target = _check_report_target(user, body.target_type, body.target_id)
    report = Report(
        reporter_id=user.id,
        target_type=body.target_type,
        target_id=body.target_id,
        reason=body.reason,
        details=body.details,
    )
    db.session.add(report)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("conflict", "You already have an open report for this.", 409) from e

    if body.target_type == "resource" and body.reason in ("broken_link", "outdated"):
        from app.modules.resources.models import Resource

        bump(Resource, target.id, "broken_report_count", 1)
        # Queue for an immediate re-check: the link-check job picks resources with open broken reports.
    if body.reason in ("spam", "abuse") and body.target_type in MODERATABLE:
        _maybe_auto_hide(body.target_type, target)
    db.session.commit()
    return report


def _maybe_auto_hide(target_type: str, target) -> None:
    distinct_reporters = db.session.execute(
        select(func.count(func.distinct(Report.reporter_id))).where(
            Report.target_type == target_type,
            Report.target_id == target.id,
            Report.status == "open",
            Report.reason.in_(("spam", "abuse")),
        )
    ).scalar_one()
    attr = _status_attr(target_type)
    if distinct_reporters >= AUTO_HIDE_THRESHOLD and getattr(target, attr) == "published":
        setattr(target, attr, "hidden")
        system = get_system_user()
        if system is not None:
            log_action(system.id, "hide", target_type, target.id, "auto_hide", {"open_reports": distinct_reporters})
        notify(owner_id_of(target), system, "content_moderated", target_type, target, snippet_text="hidden pending review")


def resolve_report(actor, report_id, status: str, note: str | None) -> Report:
    report = db.session.execute(select(Report).where(Report.id == report_id).with_for_update()).scalar_one_or_none()
    if report is None:
        raise not_found()
    if report.status != "open":
        raise ApiError("conflict", f"Report is already {report.status}.", 409)
    report.status = status
    report.resolution_note = note
    report.resolved_by = actor.id
    report.resolved_at = datetime.now(UTC)
    if report.target_type == "resource" and report.reason in ("broken_link", "outdated"):
        from app.modules.resources.models import Resource

        bump(Resource, report.target_id, "broken_report_count", -1)
    log_action(actor.id, "resolve_report" if status == "resolved" else "dismiss_report", "report", report.id, note)
    db.session.commit()
    return report


def target_preview(target_type: str, target_id) -> dict:
    from app.modules.ai.models import AIDraft

    model = model_for(target_type)
    obj = db.session.get(model, target_id)
    if obj is None:
        return {"exists": False}
    if target_type == "ai_message":
        return {"exists": True, "title": f"AI {obj.role} message", "content": obj.content, "status": obj.status}
    if target_type == "ai_draft":
        assert isinstance(obj, AIDraft)
        return {
            "exists": True,
            "title": obj.title,
            "content": json.dumps(obj.output)[:5000],
            "status": obj.status,
        }
    if target_type == "user":
        return {"exists": True, "title": obj.display_name, "author": user_summary(obj), "status": obj.status}
    author = load_users([owner_id_of(obj)]).get(owner_id_of(obj))
    text = (
        getattr(obj, "body", None)
        or getattr(obj, "short_description", None)
        or getattr(obj, "problem_statement", None)
        or getattr(obj, "description", None)
        or getattr(obj, "what_tested", None)
    )
    return {
        "exists": True,
        "title": title_of(target_type, obj),
        "snippet": snippet(text, 280),
        "author": user_summary(author),
        "status": getattr(obj, _status_attr(target_type), None),
        "deleted": getattr(obj, "deleted_at", None) is not None,
        "url_path": url_path_of(target_type, obj),
    }


def serialize_reports(reports: list[Report], include_preview: bool = True) -> list[dict]:
    users = load_users(r.reporter_id for r in reports)
    out = []
    for r in reports:
        item = {
            "id": str(r.id),
            "reporter": user_summary(users.get(r.reporter_id)),
            "target_type": r.target_type,
            "target_id": str(r.target_id),
            "reason": r.reason,
            "details": r.details,
            "status": r.status,
            "resolution_note": r.resolution_note,
            "resolved_at": r.resolved_at,
            "created_at": r.created_at,
        }
        if include_preview:
            item["target_preview"] = target_preview(r.target_type, r.target_id)
        out.append(item)
    return out


# Moderation ------------------------------------------------------------------------------


def moderate(actor, target_type: str, target_id, action: str, reason: str | None) -> dict:
    if target_type not in MODERATABLE:
        raise bad_request("This content type cannot be moderated.")
    if action in ("feature", "unfeature") and target_type not in FEATURABLE:
        raise bad_request("Only harnesses, ideas, resources and collections can be featured.")
    model = model_for(target_type)
    obj = db.session.execute(select(model).where(model.id == target_id).with_for_update()).scalar_one_or_none()
    if obj is None or getattr(obj, "deleted_at", None) is not None:
        raise not_found()
    attr = _status_attr(target_type)
    previous = getattr(obj, attr)
    if action == "hide":
        setattr(obj, attr, "hidden")
    elif action == "restore":
        setattr(obj, attr, "published")
    elif action == "remove":
        setattr(obj, attr, "removed")
    elif action == "feature":
        obj.is_featured = True
    elif action == "unfeature":
        obj.is_featured = False
    log_action(actor.id, action, target_type, obj.id, reason, {"previous_status": previous})
    if action in ("hide", "restore", "remove"):
        notify(
            owner_id_of(obj),
            actor,
            "content_moderated",
            target_type,
            obj,
            snippet_text=f"{action}: {reason}" if reason else action,
        )
    db.session.commit()
    return {
        "target_type": target_type,
        "target_id": str(obj.id),
        "status": getattr(obj, attr),
        "is_featured": getattr(obj, "is_featured", None),
    }
