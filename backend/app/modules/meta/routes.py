"""Health, config, tags, home and global search (spec §8.2, §11)."""

from __future__ import annotations

from typing import Literal

from flask import Blueprint, g
from pydantic import Field
from sqlalchemy import func, literal_column, select, text

from app.auth.decorators import optional_auth
from app.common import enums
from app.common.content import public_clause
from app.common.listing import fts, sort_columns
from app.common.responses import ok
from app.common.validation import CsvList, QueryModel, validate_query
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.meta.models import Category

bp = Blueprint("meta", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    return ok({"status": "ok"})


@bp.get("/health/ready")
def ready():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        from flask import jsonify

        resp = jsonify({"data": {"status": "unavailable"}})
        resp.status_code = 503
        return resp
    return ok({"status": "ok", "database": "ok"})


@bp.get("/meta/config")
def config():
    s = get_settings()
    cats = db.session.execute(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.module, Category.sort_order)
    ).scalars()
    categories: dict[str, list] = {m: [] for m in enums.CATEGORY_MODULES}
    for c in cats:
        categories[c.module].append({"slug": c.slug, "name": c.name, "description": c.description})
    categories["collection"] = categories["resource"]
    from app.modules.ai.quota import ai_status_reason

    reason = ai_status_reason()
    return ok(
        {
            "app_name": s.APP_NAME,
            "categories": categories,
            "enums": {
                "tools": enums.TOOLS,
                "component_types": enums.COMPONENT_TYPES,
                "collaboration_statuses": enums.COLLABORATION_STATUSES,
                "resource_types": enums.RESOURCE_TYPES,
                "resource_levels": enums.RESOURCE_LEVELS,
                "link_statuses": enums.LINK_STATUSES,
                "collection_visibility": enums.COLLECTION_VISIBILITY,
                "suggestion_kinds": enums.SUGGESTION_KINDS,
                "suggestion_statuses": enums.SUGGESTION_STATUSES,
                "collab_request_statuses": enums.COLLAB_STATUSES,
                "report_targets": enums.REPORT_TARGETS,
                "report_reasons": enums.REPORT_REASONS,
                "notification_types": enums.NOTIFICATION_TYPES,
                "contact_visibility": enums.CONTACT_VISIBILITY,
                "roles": enums.ROLES,
                "content_statuses": enums.CONTENT_STATUSES,
                "ai_refine_actions": enums.AI_REFINE_ACTIONS,
                "ai_feedback_categories": enums.AI_FEEDBACK_CATEGORIES,
                "ai_verification_statuses": enums.AI_VERIFICATION_STATUSES,
                "ai_draft_tasks": enums.AI_DRAFT_TASKS,
                "moderate_actions": enums.MODERATE_ACTIONS,
            },
            "limits": {**enums.LIMITS, "ai_chat_message": {"min": 1, "max": s.AI_MAX_INPUT_CHARS}},
            "sorts": enums.SORTS,
            "reserved_usernames": sorted(enums.RESERVED_USERNAMES),
            "ai": {"enabled": reason is None, "model_label": s.AI_MODEL_LABEL, "reason": reason},
        }
    )


class TagsQuery(QueryModel):
    module: Literal["harness", "idea", "resource", "collection"] = "harness"
    q: str = ""
    limit: int = Field(10, ge=1, le=50)


def _module_model(module: str):
    from app.modules.collections.models import Collection
    from app.modules.harnesses.models import Harness
    from app.modules.ideas.models import Idea
    from app.modules.resources.models import Resource

    return {"harness": Harness, "idea": Idea, "resource": Resource, "collection": Collection}[module]


@bp.get("/tags")
@validate_query(TagsQuery)
def tags(query: TagsQuery):
    model = _module_model(query.module)
    tag = func.unnest(model.tags).label("tag")
    sub = select(tag).where(public_clause(model)).subquery()
    stmt = select(sub.c.tag, func.count().label("count")).group_by(sub.c.tag)
    q = query.q.strip().lower()
    if q:
        stmt = stmt.where(sub.c.tag.like(q.replace("%", "").replace("_", r"\_") + "%"))
    rows = db.session.execute(stmt.order_by(literal_column("count").desc(), sub.c.tag).limit(query.limit)).all()
    return ok([{"tag": t, "count": c} for t, c in rows])


def _top(model, extra, order, limit=5):
    stmt = select(model).where(public_clause(model), *extra).order_by(*order).limit(limit)
    return db.session.execute(stmt).scalars().all()


@bp.get("/home")
@optional_auth
def home():
    from app.modules.collections.models import Collection
    from app.modules.collections.service import summaries as coll_sum
    from app.modules.harnesses.models import Harness
    from app.modules.harnesses.service import summaries as h_sum
    from app.modules.ideas.models import Idea
    from app.modules.ideas.service import summaries as i_sum
    from app.modules.resources.models import Resource
    from app.modules.resources.service import summaries as r_sum

    viewer = g.current_user
    modules = {
        "harnesses": (Harness, h_sum, []),
        "ideas": (Idea, i_sum, []),
        "resources": (Resource, r_sum, []),
        "collections": (Collection, coll_sum, [Collection.visibility == "public"]),
    }
    out: dict = {}
    for key, (model, summarize, extra) in modules.items():
        out[key] = {
            "featured": summarize(_top(model, [*extra, model.is_featured.is_(True)], sort_columns(model, "recent")), viewer),
            "trending": summarize(_top(model, extra, sort_columns(model, "trending")), viewer),
            "recent": summarize(_top(model, extra, sort_columns(model, "recent")), viewer),
        }
    counts = {
        key: db.session.execute(select(func.count()).select_from(model).where(public_clause(model), *extra)).scalar_one()
        for key, (model, _s, extra) in modules.items()
    }
    from app.modules.users.models import User

    counts["members"] = db.session.execute(
        select(func.count()).select_from(User).where(User.status == "active")
    ).scalar_one()
    out["counts"] = counts
    return ok(out)


class SearchQuery(QueryModel):
    q: str = ""
    types: CsvList = Field(default_factory=lambda: ["harness", "idea", "resource", "collection"])
    limit: int = Field(5, ge=1, le=20)


@bp.get("/search")
@optional_auth
@validate_query(SearchQuery)
def search(query: SearchQuery):
    from app.modules.collections.models import Collection
    from app.modules.collections.service import summaries as coll_sum
    from app.modules.harnesses.models import Harness
    from app.modules.harnesses.service import summaries as h_sum
    from app.modules.ideas.models import Idea
    from app.modules.ideas.service import summaries as i_sum
    from app.modules.resources.models import Resource
    from app.modules.resources.service import summaries as r_sum

    q = query.q.strip()
    mapping = {
        "harness": ("harnesses", Harness, h_sum, []),
        "idea": ("ideas", Idea, i_sum, []),
        "resource": ("resources", Resource, r_sum, []),
        "collection": ("collections", Collection, coll_sum, [Collection.visibility == "public"]),
    }
    out: dict = {}
    for t in query.types:
        if t not in mapping:
            continue
        key, model, summarize, extra = mapping[t]
        if not q:
            out[key] = []
            continue
        clause, rank = fts(model, q)
        rows = db.session.execute(
            select(model)
            .where(public_clause(model), clause, *extra)
            .order_by(rank.desc(), model.created_at.desc())
            .limit(query.limit)
        ).scalars().all()
        out[key] = summarize(rows, g.current_user)
    return ok(out)
