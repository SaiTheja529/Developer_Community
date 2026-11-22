"""Curated collections with ordered items (spec §8.7)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update

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
from app.common.errors import ApiError, conflict, forbidden, not_found, validation_error
from app.common.listing import apply_sort, author_filter, category_filter, fts, tag_list_filter
from app.common.text import slugify
from app.extensions import db
from app.modules.ai.drafts import claim_draft, mark_published
from app.modules.collections.models import Collection, CollectionItem
from app.modules.resources.models import Resource

MAX_ITEMS = 100


def summaries(items: list[Collection], viewer) -> list[dict]:
    users = load_users(c.owner_id for c in items)
    cats = categories_by_id(c.category_id for c in items)
    states = viewer_states("collection", items, viewer)
    return [
        {
            "id": str(c.id),
            "slug": c.slug,
            "title": c.title,
            "description": c.description,
            "category": category_dict(cats.get(c.category_id)),
            "tags": c.tags,
            "visibility": c.visibility,
            "owner": user_summary(users.get(c.owner_id)),
            "counts": {
                "items": c.item_count,
                "votes": c.vote_count,
                "comments": c.comment_count,
                "bookmarks": c.bookmark_count,
            },
            "ai_assisted": c.ai_assisted,
            "is_featured": c.is_featured,
            "status": c.status,
            "created_at": c.created_at,
            "updated_at": c.updated_at,
            "viewer": states[c.id],
        }
        for c in items
    ]


def _items(c: Collection, viewer) -> list[dict]:
    from app.modules.resources.service import summaries as resource_summaries

    rows = db.session.execute(
        select(CollectionItem).where(CollectionItem.collection_id == c.id).order_by(CollectionItem.position)
    ).scalars().all()
    resources = {
        r.id: r
        for r in db.session.execute(select(Resource).where(Resource.id.in_([i.resource_id for i in rows]))).scalars()
    }
    visible = [r for r in resources.values() if can_view(r, viewer) and r.status == "published"]
    summaries_by_id = {r.id: s for r, s in zip(visible, resource_summaries(visible, viewer), strict=True)}
    return [
        {
            "resource_id": str(i.resource_id),
            "position": i.position,
            "note": i.note,
            "added_at": i.added_at,
            "resource": summaries_by_id.get(i.resource_id),
            "unavailable": i.resource_id not in summaries_by_id,
        }
        for i in rows
    ]


def detail(c: Collection, viewer) -> dict:
    data = summaries([c], viewer)[0]
    data["items"] = _items(c, viewer)
    return data


def list_collections(query, viewer):
    stmt = select(Collection).where(public_clause(Collection), Collection.visibility == "public")
    rank = None
    if query.q:
        clause, rank = fts(Collection, query.q)
        stmt = stmt.where(clause)
    if query.category:
        stmt = stmt.where(category_filter(Collection, "resource", query.category))
    if (c := tag_list_filter(Collection, "tags", query.tags, "all")) is not None:
        stmt = stmt.where(c)
    if query.author:
        stmt = stmt.where(author_filter(Collection, "owner_id", query.author.lower()))
    if query.featured:
        stmt = stmt.where(Collection.is_featured.is_(True))
    return apply_sort(stmt, Collection, query.sort, SORTS["collections"], rank)


def _load_resource_for_item(resource_id, viewer) -> Resource:
    r = db.session.get(Resource, resource_id)
    if r is None or not can_view(r, viewer) or r.status != "published":
        raise validation_error({"resource_id": "Unknown or unavailable resource."})
    return r


def create(user, body) -> Collection:
    cat = category_by_slug("resource", body.category)
    draft = claim_draft(body.source_draft_id, user, ("resource_recommendations",))
    items = body.items or []
    if len(items) > MAX_ITEMS:
        raise validation_error({"items": f"At most {MAX_ITEMS} items."})
    seen = set()
    for it in items:
        if it.resource_id in seen:
            raise validation_error({"items": "Each resource can appear only once."})
        seen.add(it.resource_id)
        _load_resource_for_item(it.resource_id, user)
    c = Collection(
        slug=slugify(body.title),
        owner_id=user.id,
        title=body.title,
        description=body.description,
        category_id=cat.id,
        tags=body.tags,
        visibility=body.visibility,
        ai_assisted=bool(body.ai_assisted or draft is not None),
        source_draft_id=draft.id if draft else None,
        item_count=len(items),
    )
    db.session.add(c)
    db.session.flush()
    for pos, it in enumerate(items):
        db.session.add(CollectionItem(collection_id=c.id, resource_id=it.resource_id, position=pos, note=it.note))
        bump(Resource, it.resource_id, "collection_count", 1)
    mark_published(draft, "collection", c.id)
    db.session.commit()
    return c


def get_for_owner(collection_id, user) -> Collection:
    c = get_or_404(Collection, collection_id, user, lock=True)
    if c.owner_id != user.id:
        raise forbidden("Only the owner can edit this collection.")
    return c


def update_collection(c: Collection, body) -> Collection:
    data = body.model_dump(exclude_unset=True)
    if "category" in data:
        c.category_id = category_by_slug("resource", data.pop("category")).id
    if data.pop("ai_assisted", None):
        c.ai_assisted = True
    for k, v in data.items():
        setattr(c, k, v)
    if "title" in data:
        c.slug = slugify(c.title)
    db.session.commit()
    return c


def soft_delete(collection_id, user) -> None:
    c = get_or_404(Collection, collection_id, user, lock=True)
    if c.owner_id != user.id and not is_mod(user):
        raise forbidden()
    c.deleted_at = datetime.now(UTC)
    db.session.commit()


def add_item(c: Collection, user, body) -> None:
    _load_resource_for_item(body.resource_id, user)
    count = db.session.execute(
        select(func.count()).select_from(CollectionItem).where(CollectionItem.collection_id == c.id)
    ).scalar_one()
    if count >= MAX_ITEMS:
        raise ApiError("validation_error", f"A collection can hold at most {MAX_ITEMS} items.", 422,
                       {"fields": {"items": f"At most {MAX_ITEMS} items."}})
    exists = db.session.get(CollectionItem, (c.id, body.resource_id))
    if exists is not None:
        raise conflict("This resource is already in the collection.")
    position = count if body.position is None else max(0, min(body.position, count))
    if position < count:
        db.session.execute(
            update(CollectionItem)
            .where(CollectionItem.collection_id == c.id, CollectionItem.position >= position)
            .values(position=CollectionItem.position + 1)
        )
    db.session.add(CollectionItem(collection_id=c.id, resource_id=body.resource_id, position=position, note=body.note))
    bump(Collection, c.id, "item_count", 1)
    bump(Resource, body.resource_id, "collection_count", 1)
    c.updated_at = func.now()
    db.session.commit()


def update_item(c: Collection, resource_id, note) -> None:
    item = db.session.get(CollectionItem, (c.id, resource_id))
    if item is None:
        raise not_found("Item not found.")
    item.note = note
    c.updated_at = func.now()
    db.session.commit()


def _densify(collection_id) -> None:
    rows = db.session.execute(
        select(CollectionItem).where(CollectionItem.collection_id == collection_id).order_by(CollectionItem.position)
    ).scalars().all()
    for pos, item in enumerate(rows):
        item.position = pos


def remove_item(c: Collection, resource_id) -> None:
    res = db.session.execute(
        delete(CollectionItem).where(CollectionItem.collection_id == c.id, CollectionItem.resource_id == resource_id)
    )
    if not res.rowcount:
        raise not_found("Item not found.")
    bump(Collection, c.id, "item_count", -1)
    bump(Resource, resource_id, "collection_count", -1)
    _densify(c.id)
    c.updated_at = func.now()
    db.session.commit()


def reorder(c: Collection, resource_ids: list) -> None:
    rows = db.session.execute(select(CollectionItem).where(CollectionItem.collection_id == c.id)).scalars().all()
    current = {i.resource_id for i in rows}
    if len(resource_ids) != len(set(resource_ids)) or set(resource_ids) != current:
        raise validation_error({"resource_ids": "Must contain exactly the current items, each once."})
    by_id = {i.resource_id: i for i in rows}
    for pos, rid in enumerate(resource_ids):
        by_id[rid].position = pos
    c.updated_at = func.now()
    db.session.commit()
