"""/api/admin/* moderation and administration endpoints (spec §8.13)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

from flask import Blueprint, g
from sqlalchemy import cast, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.types import Date

from app.auth import sessions
from app.auth.decorators import require_auth, require_role
from app.common.content import load_users, user_summary
from app.common.errors import ApiError, bad_request, not_found
from app.common.pagination import PageParams, paginate
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import OptText, StrictModel, Text, parse_body, validate_query
from app.extensions import db
from app.modules.meta.models import TrustedDomain
from app.modules.reports import service as reports
from app.modules.reports.models import ModerationAction, Report
from app.modules.users.models import User

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


# Reports ---------------------------------------------------------------------------------


class ReportsQuery(PageParams):
    status: Literal["open", "resolved", "dismissed"] = "open"
    target_type: str | None = None


class ReportPatch(StrictModel):
    status: Literal["resolved", "dismissed"]
    resolution_note: OptText(2000) = None


@bp.get("/reports")
@require_auth
@require_role("moderator")
@validate_query(ReportsQuery)
def list_reports(query: ReportsQuery):
    stmt = select(Report).where(Report.status == query.status)
    if query.target_type:
        stmt = stmt.where(Report.target_type == query.target_type)
    stmt = stmt.order_by(Report.created_at.asc() if query.status == "open" else Report.created_at.desc())
    page = paginate(stmt, query.page, query.page_size)
    return paginated(reports.serialize_reports(page.items), page.page, page.page_size, page.total)


@bp.patch("/reports/<uuid:report_id>")
@require_auth
@require_role("moderator")
def patch_report(report_id: uuid.UUID):
    body = parse_body(ReportPatch)
    report = reports.resolve_report(g.current_user, report_id, body.status, body.resolution_note)
    return ok(reports.serialize_reports([report])[0])


class ModerateBody(StrictModel):
    target_type: Literal["harness", "idea", "resource", "collection", "comment", "suggestion", "review"]
    target_id: uuid.UUID
    action: Literal["hide", "restore", "remove", "feature", "unfeature"]
    reason: OptText(1000) = None


@bp.post("/moderate")
@require_auth
@require_role("moderator")
def moderate():
    body = parse_body(ModerateBody)
    return ok(reports.moderate(g.current_user, body.target_type, body.target_id, body.action, body.reason))


@bp.get("/moderation-log")
@require_auth
@require_role("moderator")
@validate_query(PageParams)
def moderation_log(query: PageParams):
    page = paginate(select(ModerationAction).order_by(ModerationAction.created_at.desc()), query.page, query.page_size)
    actors = load_users(a.actor_id for a in page.items)
    items = [
        {
            "id": str(a.id),
            "actor": user_summary(actors.get(a.actor_id)),
            "action": a.action,
            "target_type": a.target_type,
            "target_id": str(a.target_id),
            "reason": a.reason,
            "metadata": a.metadata_,
            "created_at": a.created_at,
        }
        for a in page.items
    ]
    return paginated(items, page.page, page.page_size, page.total)


# Users -----------------------------------------------------------------------------------


class UsersQuery(PageParams):
    q: str | None = None
    status: Literal["active", "suspended", "deleted"] | None = None
    role: Literal["user", "moderator", "admin"] | None = None


class UserPatch(StrictModel):
    status: Literal["active", "suspended"] | None = None
    role: Literal["user", "moderator", "admin"] | None = None
    reason: Text(1, 1000)


def _admin_user_dict(u: User) -> dict:
    return {
        **user_summary(u),
        "email": u.email,
        "email_verified": u.email_verified_at is not None,
        "role": u.role,
        "status": u.status,
        "created_at": u.created_at,
        "last_login_at": u.last_login_at,
        "last_seen_at": u.last_seen_at,
    }


@bp.get("/users")
@require_auth
@require_role("admin")
@validate_query(UsersQuery)
def list_users(query: UsersQuery):
    stmt = select(User)
    if query.q:
        like = f"%{query.q.strip().lower()}%"
        stmt = stmt.where(
            or_(User.username.ilike(like), User.display_name.ilike(like), User.email.ilike(like))
        )
    if query.status:
        stmt = stmt.where(User.status == query.status)
    if query.role:
        stmt = stmt.where(User.role == query.role)
    page = paginate(stmt.order_by(User.created_at.desc()), query.page, query.page_size)
    return paginated([_admin_user_dict(u) for u in page.items], page.page, page.page_size, page.total)


@bp.patch("/users/<uuid:user_id>")
@require_auth
@require_role("admin")
def patch_user(user_id: uuid.UUID):
    body = parse_body(UserPatch)
    user = db.session.execute(select(User).where(User.id == user_id).with_for_update()).scalar_one_or_none()
    if user is None or user.status == "deleted" or user.username == reports.SYSTEM_USERNAME:
        raise not_found()
    if user.id == g.current_user.id:
        raise bad_request("You cannot change your own role or status.")
    if body.status is None and body.role is None:
        raise bad_request("Provide status and/or role.")
    if body.status is not None and body.status != user.status:
        previous = user.status
        user.status = body.status
        if body.status == "suspended":
            sessions.revoke_user_sessions(user.id, "suspended")
        reports.log_action(
            g.current_user.id,
            "suspend_user" if body.status == "suspended" else "unsuspend_user",
            "user",
            user.id,
            body.reason,
            {"previous_status": previous},
        )
    if body.role is not None and body.role != user.role:
        previous = user.role
        user.role = body.role
        reports.log_action(g.current_user.id, "set_role", "user", user.id, body.reason, {"previous_role": previous, "role": body.role})
    db.session.commit()
    return ok(_admin_user_dict(user))


# Resources & trusted domains -------------------------------------------------------------


class OfficialBody(StrictModel):
    official_verified: bool


@bp.post("/resources/<uuid:resource_id>/official")
@require_auth
@require_role("moderator")
def set_official(resource_id: uuid.UUID):
    from app.modules.resources.models import Resource
    from app.modules.resources.service import detail

    body = parse_body(OfficialBody)
    r = db.session.get(Resource, resource_id)
    if r is None or r.deleted_at is not None:
        raise not_found()
    r.official_verified = body.official_verified
    reports.log_action(g.current_user.id, "set_official", "resource", r.id, None, {"official_verified": body.official_verified})
    db.session.commit()
    return ok(detail(r, g.current_user))


class TrustedDomainBody(StrictModel):
    domain: Text(3, 253)
    kind: Literal["official_docs", "reputable"]
    label: OptText(100) = None


@bp.get("/trusted-domains")
@require_auth
@require_role("admin")
def list_trusted_domains():
    rows = db.session.execute(select(TrustedDomain).order_by(TrustedDomain.domain)).scalars().all()
    return ok([r.to_dict() for r in rows])


@bp.post("/trusted-domains")
@require_auth
@require_role("admin")
def add_trusted_domain():
    body = parse_body(TrustedDomainBody)
    domain = body.domain.lower().strip().removeprefix("www.").rstrip(".")
    if "/" in domain or ":" in domain or "." not in domain:
        raise ApiError("validation_error", "Some fields are invalid.", 400, {"fields": {"domain": "Use a bare host name."}})
    row = TrustedDomain(domain=domain, kind=body.kind, label=body.label, added_by=g.current_user.id)
    db.session.add(row)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("conflict", "This domain is already trusted.", 409) from e
    db.session.commit()
    return created(row.to_dict())


@bp.delete("/trusted-domains/<int:domain_id>")
@require_auth
@require_role("admin")
def delete_trusted_domain(domain_id: int):
    row = db.session.get(TrustedDomain, domain_id)
    if row is None:
        raise not_found()
    db.session.delete(row)
    db.session.commit()
    return no_content()


# Stats -----------------------------------------------------------------------------------


@bp.get("/stats")
@require_auth
@require_role("admin")
def stats():
    from app.modules.ai.models import AIUsage
    from app.modules.ai.quota import month_to_date_cost
    from app.modules.collections.models import Collection
    from app.modules.harnesses.models import Harness
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource

    def live(model):
        return db.session.execute(
            select(func.count()).select_from(model).where(model.deleted_at.is_(None))
        ).scalar_one()

    now = datetime.now(UTC)

    def new_users(days):
        return db.session.execute(
            select(func.count()).select_from(User).where(User.created_at >= now - timedelta(days=days))
        ).scalar_one()

    since = now - timedelta(days=30)
    daily = db.session.execute(
        select(cast(AIUsage.created_at, Date), func.count(), func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0))
        .where(AIUsage.created_at >= since)
        .group_by(cast(AIUsage.created_at, Date))
        .order_by(cast(AIUsage.created_at, Date))
    ).all()
    from app.extensions import settings

    return ok(
        {
            "counts": {
                "users": db.session.execute(select(func.count()).select_from(User).where(User.status != "deleted")).scalar_one(),
                "harnesses": live(Harness),
                "ideas": live(Idea),
                "resources": live(Resource),
                "collections": live(Collection),
            },
            "new_users": {"last_7_days": new_users(7), "last_30_days": new_users(30)},
            "open_reports": db.session.execute(
                select(func.count()).select_from(Report).where(Report.status == "open")
            ).scalar_one(),
            "ai": {
                "cost_month_to_date_usd": round(month_to_date_cost(use_cache=False), 4),
                "monthly_budget_usd": settings().AI_MONTHLY_BUDGET_USD,
                "requests_per_day": [
                    {"date": d.isoformat(), "requests": n, "cost_usd": round(float(c), 4)} for d, n, c in daily
                ],
            },
        }
    )


