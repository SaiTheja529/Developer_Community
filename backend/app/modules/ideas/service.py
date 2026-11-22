"""Project Ideas business logic (spec §8.4)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.common.content import (
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
from app.common.enums import SORTS
from app.common.errors import forbidden
from app.common.listing import apply_sort, author_filter, category_filter, fts, tag_list_filter
from app.common.text import slugify
from app.extensions import db
from app.modules.ai.drafts import claim_draft, mark_published
from app.modules.ideas.models import Idea


def summaries(items: list[Idea], viewer) -> list[dict]:
    users = load_users(i.author_id for i in items)
    cats = categories_by_id(i.category_id for i in items)
    states = viewer_states("idea", items, viewer)
    return [
        {
            "id": str(i.id),
            "slug": i.slug,
            "title": i.title,
            "problem_statement": i.problem_statement,
            "tech_stack": i.tech_stack,
            "category": category_dict(cats.get(i.category_id)),
            "tags": i.tags,
            "author": user_summary(users.get(i.author_id)),
            "collaboration_status": i.collaboration_status,
            "counts": {
                "votes": i.vote_count,
                "interest": i.interest_count,
                "comments": i.comment_count,
                "suggestions": i.suggestion_count,
                "collaborators": i.collaborator_count,
                "bookmarks": i.bookmark_count,
            },
            "ai_assisted": i.ai_assisted,
            "is_featured": i.is_featured,
            "status": i.status,
            "created_at": i.created_at,
            "updated_at": i.updated_at,
            "viewer": states[i.id],
        }
        for i in items
    ]


def detail(i: Idea, viewer) -> dict:
    from app.modules.collaborations.service import pending_count, viewer_request

    data = summaries([i], viewer)[0]
    data.update(
        {
            "proposed_solution": i.proposed_solution,
            "description": i.description,
            "expected_features": i.expected_features,
            "github_url": i.github_url,
            "last_activity_at": i.last_activity_at,
            "collaboration": {
                "status": i.collaboration_status,
                "collaborator_count": i.collaborator_count,
                "viewer_request": viewer_request("idea", i.id, viewer),
            },
        }
    )
    if viewer is not None and viewer.id == i.author_id:
        data["collaboration"]["pending_requests"] = pending_count("idea", i.id)
    return data


def list_ideas(query, viewer):
    stmt = select(Idea).where(public_clause(Idea))
    rank = None
    if query.q:
        clause, rank = fts(Idea, query.q)
        stmt = stmt.where(clause)
    if query.category:
        stmt = stmt.where(category_filter(Idea, "idea", query.category))
    if (c := tag_list_filter(Idea, "tags", query.tags, "all")) is not None:
        stmt = stmt.where(c)
    if (c := tag_list_filter(Idea, "tech_stack", query.tech, "any")) is not None:
        stmt = stmt.where(c)
    if query.author:
        stmt = stmt.where(author_filter(Idea, "author_id", query.author.lower()))
    if query.collaboration_status:
        stmt = stmt.where(Idea.collaboration_status == query.collaboration_status)
    if query.featured:
        stmt = stmt.where(Idea.is_featured.is_(True))
    return apply_sort(stmt, Idea, query.sort, SORTS["ideas"], rank)


def create(user, body) -> Idea:
    cat = category_by_slug("idea", body.category)
    draft = claim_draft(body.source_draft_id, user, ("project_idea",))
    idea = Idea(
        slug=slugify(body.title),
        author_id=user.id,
        title=body.title,
        problem_statement=body.problem_statement,
        proposed_solution=body.proposed_solution,
        description=body.description,
        tech_stack=body.tech_stack,
        expected_features=[f.model_dump() for f in body.expected_features],
        category_id=cat.id,
        tags=body.tags,
        github_url=body.github_url,
        collaboration_status=body.collaboration_status,
        ai_assisted=bool(body.ai_assisted or draft is not None),
        source_draft_id=draft.id if draft else None,
    )
    db.session.add(idea)
    db.session.flush()
    mark_published(draft, "idea", idea.id)
    db.session.commit()
    return idea


def get_for_owner(idea_id, user) -> Idea:
    idea = get_or_404(Idea, idea_id, user, lock=True)
    if idea.author_id != user.id:
        raise forbidden("Only the author can edit this idea.")
    return idea


def update_idea(idea: Idea, body) -> Idea:
    data = body.model_dump(exclude_unset=True)
    if "category" in data:
        idea.category_id = category_by_slug("idea", data.pop("category")).id
    if "expected_features" in data:
        data["expected_features"] = [dict(f) for f in data["expected_features"]]
    if data.pop("ai_assisted", None):
        idea.ai_assisted = True
    for k, v in data.items():
        setattr(idea, k, v)
    if "title" in data:
        idea.slug = slugify(idea.title)
    db.session.commit()
    return idea


def soft_delete(idea_id, user) -> None:
    from app.modules.collaborations.service import withdraw_pending_for_target

    idea = get_or_404(Idea, idea_id, user, lock=True)
    if idea.author_id != user.id and not is_mod(user):
        raise forbidden()
    idea.deleted_at = datetime.now(UTC)
    withdraw_pending_for_target("idea", idea.id)
    db.session.commit()
