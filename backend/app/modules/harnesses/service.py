"""Harness Lab business logic (spec §8.3)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.common.content import (
    can_view,
    categories_by_id,
    category_by_slug,
    category_dict,
    get_or_404,
    is_mod,
    load_users,
    public_clause,
    user_summary,
    viewer_states,
)
from app.common.counters import bump
from app.common.enums import SORTS
from app.common.errors import ApiError, duplicate, forbidden, not_found
from app.common.listing import apply_sort, author_filter, category_filter, fts, tag_list_filter
from app.common.text import slugify
from app.extensions import db
from app.integrations.github import fetch_repo_for_submission
from app.modules.ai.drafts import claim_draft, mark_published
from app.modules.harnesses.models import Harness, HarnessReview
from app.modules.notifications.service import notify

# Serialization ----------------------------------------------------------------------------


def _repo_summary(h: Harness) -> dict:
    m = h.repo_metadata or {}
    return {
        "url": h.repo_url,
        "owner": h.repo_owner,
        "name": h.repo_name,
        "stars": m.get("stars"),
        "language": m.get("language"),
    }


def _repo_full(h: Harness) -> dict:
    m = h.repo_metadata or {}
    return {
        **_repo_summary(h),
        "forks": m.get("forks"),
        "license": m.get("license"),
        "topics": m.get("topics", []),
        "pushed_at": m.get("pushed_at"),
        "archived": bool(m.get("archived")),
        "description": m.get("description"),
        "default_branch": m.get("default_branch"),
        "unavailable": bool(m.get("unavailable")),
        "fetched_at": h.repo_metadata_fetched_at,
    }


def summaries(items: list[Harness], viewer) -> list[dict]:
    users = load_users(h.author_id for h in items)
    cats = categories_by_id(h.category_id for h in items)
    states = viewer_states("harness", items, viewer)
    return [
        {
            "id": str(h.id),
            "slug": h.slug,
            "name": h.name,
            "short_description": h.short_description,
            "tools": h.tools,
            "category": category_dict(cats.get(h.category_id)),
            "tags": h.tags,
            "author": user_summary(users.get(h.author_id)),
            "repo": _repo_summary(h),
            "counts": {
                "votes": h.vote_count,
                "comments": h.comment_count,
                "suggestions": h.suggestion_count,
                "reviews": h.review_count,
                "bookmarks": h.bookmark_count,
            },
            "ai_assisted": h.ai_assisted,
            "is_featured": h.is_featured,
            "status": h.status,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
            "viewer": states[h.id],
        }
        for h in items
    ]


def rating_summary(harness_id) -> dict:
    dims = ["overall", "documentation", "setup", "coordination", "reliability"]
    cols = []
    for d in dims:
        col = getattr(HarnessReview, f"rating_{d}")
        cols.append(func.avg(col).filter(col.isnot(None)))
        cols.append(func.count(col))
    row = db.session.execute(
        select(func.count(HarnessReview.id), *cols).where(
            HarnessReview.harness_id == harness_id, public_clause(HarnessReview)
        )
    ).one()
    out: dict = {"count": row[0], "counts": {}}
    for i, d in enumerate(dims):
        avg, cnt = row[1 + 2 * i], row[2 + 2 * i]
        out[d] = round(float(avg), 1) if avg is not None else None
        out["counts"][d] = cnt
    return out


def detail(h: Harness, viewer) -> dict:
    data = summaries([h], viewer)[0]
    data["repo"] = _repo_full(h)
    data.update(
        {
            "detailed_explanation": h.detailed_explanation,
            "architecture": h.architecture,
            "components": h.components,
            "setup_instructions": h.setup_instructions,
            "limitations": h.limitations,
            "accepts_collaboration": h.accepts_collaboration,
            "rating_summary": rating_summary(h.id),
            "last_activity_at": h.last_activity_at,
        }
    )
    if viewer is not None and h.accepts_collaboration:
        from app.modules.collaborations.service import viewer_request

        data["collaboration"] = {"viewer_request": viewer_request("harness", h.id, viewer)}
    return data


# Queries ----------------------------------------------------------------------------------


def list_harnesses(query, viewer):
    stmt = select(Harness).where(public_clause(Harness))
    rank = None
    if query.q:
        clause, rank = fts(Harness, query.q)
        stmt = stmt.where(clause)
    if query.category:
        stmt = stmt.where(category_filter(Harness, "harness", query.category))
    if (c := tag_list_filter(Harness, "tags", query.tags, "all")) is not None:
        stmt = stmt.where(c)
    if (c := tag_list_filter(Harness, "tools", query.tools, "any")) is not None:
        stmt = stmt.where(c)
    if query.author:
        stmt = stmt.where(author_filter(Harness, "author_id", query.author.lower()))
    if query.featured:
        stmt = stmt.where(Harness.is_featured.is_(True))
    return apply_sort(stmt, Harness, query.sort, SORTS["harnesses"], rank)


def find_by_repo(owner: str, repo: str, exclude_id=None) -> Harness | None:
    stmt = select(Harness).where(
        func.lower(Harness.repo_owner) == owner.lower(),
        func.lower(Harness.repo_name) == repo.lower(),
        Harness.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(Harness.id != exclude_id)
    return db.session.execute(stmt).scalars().first()


# Mutations --------------------------------------------------------------------------------


def create(user, body) -> Harness:
    ref, meta = fetch_repo_for_submission(body.repo_url)
    existing = find_by_repo(ref.owner, ref.repo)
    if existing is not None:
        raise duplicate(existing.id, "This repository is already listed. Leave a review or suggestion instead.")
    cat = category_by_slug("harness", body.category)
    draft = claim_draft(body.source_draft_id, user, ("harness_doc",))
    h = Harness(
        slug=slugify(body.name),
        author_id=user.id,
        name=body.name,
        repo_url=ref.canonical_url,
        repo_owner=ref.owner,
        repo_name=ref.repo,
        short_description=body.short_description,
        detailed_explanation=body.detailed_explanation,
        architecture=body.architecture,
        components=[c.model_dump() for c in body.components],
        setup_instructions=body.setup_instructions,
        limitations=body.limitations,
        tools=list(body.tools),
        category_id=cat.id,
        tags=body.tags,
        accepts_collaboration=body.accepts_collaboration,
        repo_metadata=meta,
        repo_metadata_fetched_at=datetime.now(UTC),
        ai_assisted=bool(body.ai_assisted or draft is not None),
        source_draft_id=draft.id if draft else None,
    )
    db.session.add(h)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        existing = find_by_repo(ref.owner, ref.repo)
        raise duplicate(existing.id if existing else "", "This repository is already listed.") from e
    mark_published(draft, "harness", h.id)
    db.session.commit()
    return h


def get_for_owner(harness_id, user) -> Harness:
    h = get_or_404(Harness, harness_id, user, lock=True)
    if h.author_id != user.id:
        raise forbidden("Only the author can edit this harness.")
    return h


def update_harness(h: Harness, user, body) -> Harness:
    data = body.model_dump(exclude_unset=True)
    if "repo_url" in data:
        ref, meta = fetch_repo_for_submission(data.pop("repo_url"))
        if (ref.owner.lower(), ref.repo.lower()) != (h.repo_owner.lower(), h.repo_name.lower()):
            existing = find_by_repo(ref.owner, ref.repo, exclude_id=h.id)
            if existing is not None:
                raise duplicate(existing.id, "This repository is already listed.")
        h.repo_url, h.repo_owner, h.repo_name = ref.canonical_url, ref.owner, ref.repo
        h.repo_metadata, h.repo_metadata_fetched_at = meta, datetime.now(UTC)
    if "category" in data:
        h.category_id = category_by_slug("harness", data.pop("category")).id
    if "components" in data:
        data["components"] = [dict(c) for c in data["components"]]
    if data.pop("ai_assisted", None):
        h.ai_assisted = True  # never cleared once set
    for k, v in data.items():
        setattr(h, k, v)
    if "name" in data:
        h.slug = slugify(h.name)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("duplicate", "This repository is already listed.", 409) from e
    return h


def soft_delete(harness_id, user) -> None:
    from app.modules.collaborations.service import withdraw_pending_for_target

    h = get_or_404(Harness, harness_id, user, lock=True)
    if h.author_id != user.id and not is_mod(user):
        raise forbidden()
    h.deleted_at = datetime.now(UTC)
    withdraw_pending_for_target("harness", h.id)
    db.session.commit()


def refresh_repo(h: Harness) -> Harness:
    from app.integrations.github import GitHubError, get_client, repo_unavailable

    try:
        meta, _ = get_client().get_repo_metadata(h.repo_owner, h.repo_name)
    except GitHubError as e:
        if e.status in ("not_found", "private"):
            h.repo_metadata = {**(h.repo_metadata or {}), "unavailable": True}
            h.repo_metadata_fetched_at = datetime.now(UTC)
            db.session.commit()
        raise repo_unavailable(e.status) from e
    h.repo_metadata = meta
    h.repo_metadata_fetched_at = datetime.now(UTC)
    db.session.commit()
    return h


# Reviews ----------------------------------------------------------------------------------


def review_dicts(reviews: list[HarnessReview], viewer) -> list[dict]:
    users = load_users(r.author_id for r in reviews)
    states = viewer_states("review", reviews, viewer)
    out = []
    for r in reviews:
        out.append(
            {
                "id": str(r.id),
                "harness_id": str(r.harness_id),
                "author": user_summary(users.get(r.author_id)),
                "what_tested": r.what_tested,
                "worked_well": r.worked_well,
                "did_not_work": r.did_not_work,
                "recommendations": r.recommendations,
                "environment": r.environment,
                "ratings": {
                    "documentation": r.rating_documentation,
                    "setup": r.rating_setup,
                    "coordination": r.rating_coordination,
                    "reliability": r.rating_reliability,
                    "overall": r.rating_overall,
                },
                "counts": {"votes": r.vote_count},
                "status": r.status,
                "disclaimer_key": "community_opinion",
                "created_at": r.created_at,
                "updated_at": r.updated_at,
                "viewer": states[r.id],
            }
        )
    return out


def list_reviews_stmt(harness_id, viewer, sort: str):
    visible = public_clause(HarnessReview)
    if viewer is not None:
        visible = or_(
            visible,
            and_(
                HarnessReview.deleted_at.is_(None),
                HarnessReview.status == "hidden",
                or_(HarnessReview.author_id == viewer.id, is_mod(viewer)),
            ),
        )
    stmt = select(HarnessReview).where(HarnessReview.harness_id == harness_id, visible)
    if sort == "recent":
        return stmt.order_by(HarnessReview.created_at.desc())
    return stmt.order_by(HarnessReview.vote_count.desc(), HarnessReview.created_at.desc())


def _apply_ratings(review: HarnessReview, ratings) -> None:
    for dim in ("documentation", "setup", "coordination", "reliability", "overall"):
        setattr(review, f"rating_{dim}", getattr(ratings, dim))


def create_review(harness_id, user, body) -> HarnessReview:
    h = get_or_404(Harness, harness_id, user, lock=True)
    if h.author_id == user.id:
        raise forbidden("You cannot review your own harness.")
    exists = db.session.execute(
        select(HarnessReview.id).where(
            HarnessReview.harness_id == h.id, HarnessReview.author_id == user.id, HarnessReview.deleted_at.is_(None)
        )
    ).first()
    if exists:
        raise ApiError("conflict", "You have already reviewed this harness. Edit your review instead.", 409,
                       {"existing_id": str(exists[0])})
    r = HarnessReview(
        harness_id=h.id,
        author_id=user.id,
        what_tested=body.what_tested,
        worked_well=body.worked_well,
        did_not_work=body.did_not_work,
        recommendations=body.recommendations,
        environment=body.environment,
    )
    _apply_ratings(r, body.ratings)
    db.session.add(r)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("conflict", "You have already reviewed this harness.", 409) from e
    bump(Harness, h.id, "review_count", 1, touch_activity=True)
    notify(h.author_id, user, "review_on_harness", "harness", h, snippet_text=body.what_tested)
    db.session.commit()
    return r


def get_review_for_edit(review_id, user, allow_mod: bool) -> HarnessReview:
    r = db.session.get(HarnessReview, review_id)
    if r is None or not can_view(r, user):
        raise not_found()
    if r.author_id != user.id and not (allow_mod and is_mod(user)):
        raise forbidden()
    return r


def update_review(r: HarnessReview, body) -> HarnessReview:
    data = body.model_dump(exclude_unset=True)
    if "ratings" in data and body.ratings is not None:
        _apply_ratings(r, body.ratings)
    data.pop("ratings", None)
    if "what_tested" in data and data["what_tested"] is None:
        data.pop("what_tested")
    for k, v in data.items():
        setattr(r, k, v)
    db.session.commit()
    return r


def delete_review(r: HarnessReview) -> None:
    r.deleted_at = datetime.now(UTC)
    bump(Harness, r.harness_id, "review_count", -1)
    db.session.commit()


def bump_activity(harness_id) -> None:
    db.session.execute(update(Harness).where(Harness.id == harness_id).values(last_activity_at=func.now()))
