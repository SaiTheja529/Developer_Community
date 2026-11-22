"""Knowledge Hub resources: URL normalization, duplicates, trusted domains, link checks (spec §8.6)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError

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
from app.common.errors import ApiError, duplicate, forbidden
from app.common.listing import apply_sort, author_filter, category_filter, fts, tag_list_filter
from app.common.text import host_matches, normalize_url, url_domain
from app.common.url_safety import static_block_reason
from app.extensions import db
from app.integrations.link_checker import apply_result, check_url
from app.modules.ai.drafts import claim_draft, mark_published
from app.modules.meta.models import TrustedDomain
from app.modules.resources.models import Resource

BROKEN_HIDE_AFTER = timedelta(days=7)


def is_official_domain(domain: str) -> bool:
    rows = db.session.execute(select(TrustedDomain.domain).where(TrustedDomain.kind == "official_docs")).scalars()
    return any(host_matches(domain, d) for d in rows)


def trusted_domain_kind(domain: str) -> str | None:
    for d, kind in db.session.execute(select(TrustedDomain.domain, TrustedDomain.kind)).all():
        if host_matches(domain, d):
            return kind
    return None


def _link(r: Resource) -> dict:
    return {
        "status": r.link_status,
        "http_status": r.link_http_status,
        "final_url": r.link_final_url,
        "last_checked_at": r.link_last_checked_at,
        "open_reports": r.broken_report_count,
    }


def summaries(items: list[Resource], viewer) -> list[dict]:
    users = load_users(r.submitter_id for r in items)
    cats = categories_by_id(r.category_id for r in items)
    states = viewer_states("resource", items, viewer)
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "url": r.url,
            "domain": r.domain,
            "description": r.description,
            "category": category_dict(cats.get(r.category_id)),
            "resource_type": r.resource_type,
            "official_verified": r.official_verified,
            "tags": r.tags,
            "level": r.level,
            "language": r.language,
            "link": _link(r),
            "submitter": user_summary(users.get(r.submitter_id)),
            "counts": {
                "votes": r.vote_count,
                "comments": r.comment_count,
                "suggestions": r.suggestion_count,
                "bookmarks": r.bookmark_count,
                "collections": r.collection_count,
            },
            "ai_assisted": r.ai_assisted,
            "is_featured": r.is_featured,
            "status": r.status,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "viewer": states[r.id],
        }
        for r in items
    ]


def detail(r: Resource, viewer) -> dict:
    from app.modules.collections.models import Collection, CollectionItem

    data = summaries([r], viewer)[0]
    cols = (
        db.session.execute(
            select(Collection)
            .join(CollectionItem, CollectionItem.collection_id == Collection.id)
            .where(
                CollectionItem.resource_id == r.id,
                public_clause(Collection),
                Collection.visibility == "public",
            )
            .order_by(Collection.vote_count.desc(), Collection.created_at.desc())
            .limit(5)
        )
        .scalars()
        .all()
    )
    data["collections_preview"] = [
        {"id": str(c.id), "slug": c.slug, "title": c.title, "item_count": c.item_count} for c in cols
    ]
    return data


def list_resources(query, viewer):
    stmt = select(Resource).where(public_clause(Resource))
    rank = None
    if query.q:
        clause, rank = fts(Resource, query.q)
        stmt = stmt.where(clause)
    if query.category:
        stmt = stmt.where(category_filter(Resource, "resource", query.category))
    if (c := tag_list_filter(Resource, "tags", query.tags, "all")) is not None:
        stmt = stmt.where(c)
    if query.resource_type:
        stmt = stmt.where(Resource.resource_type == query.resource_type)
    if query.level:
        stmt = stmt.where(Resource.level == query.level)
    if query.language:
        stmt = stmt.where(Resource.language == query.language.lower())
    if query.official:
        stmt = stmt.where(Resource.official_verified.is_(True))
    if query.domain:
        d = query.domain.lower().removeprefix("www.")
        stmt = stmt.where(or_(Resource.domain == d, Resource.domain.endswith("." + d)))
    if query.author:
        stmt = stmt.where(author_filter(Resource, "submitter_id", query.author.lower()))
    if query.link_status:
        stmt = stmt.where(Resource.link_status == query.link_status)
    if query.featured:
        stmt = stmt.where(Resource.is_featured.is_(True))
    if not query.include_broken:
        cutoff = datetime.now(UTC) - BROKEN_HIDE_AFTER
        stmt = stmt.where(
            ~and_(
                Resource.link_status.in_(("broken", "unreachable")),
                Resource.link_broken_since.isnot(None),
                Resource.link_broken_since < cutoff,
            )
        )
    return apply_sort(stmt, Resource, query.sort, SORTS["resources"], rank)


def find_duplicate(url_normalized: str, exclude_id=None) -> Resource | None:
    stmt = select(Resource).where(Resource.url_normalized == url_normalized, Resource.deleted_at.is_(None))
    if exclude_id is not None:
        stmt = stmt.where(Resource.id != exclude_id)
    return db.session.execute(stmt).scalars().first()


def _assert_not_blocked(url: str) -> None:
    reason = static_block_reason(url)
    if reason:
        raise ApiError("url_blocked", "This URL is not allowed.", 422, {"reason": reason})


def check_url_info(url: str, viewer) -> dict:
    from app.common.text import validate_http_url

    try:
        url = validate_http_url(url)
    except ValueError as e:
        return {"valid": False, "normalized": None, "duplicate": None, "blocked_reason": str(e)}
    reason = static_block_reason(url)
    normalized = normalize_url(url)
    dup = find_duplicate(normalized)
    domain = url_domain(url)
    return {
        "valid": reason is None,
        "normalized": normalized,
        "domain": domain,
        "official_domain": is_official_domain(domain),
        "duplicate": summaries([dup], viewer)[0] if dup is not None and dup.status == "published" else None,
        "blocked_reason": reason,
    }


def create(user, body) -> Resource:
    _assert_not_blocked(body.url)
    normalized = normalize_url(body.url)
    existing = find_duplicate(normalized)
    if existing is not None:
        raise duplicate(existing.id, "This resource is already in the Knowledge Hub.")
    cat = category_by_slug("resource", body.category)
    draft = claim_draft(body.source_draft_id, user, ("resource_recommendations",))
    domain = url_domain(body.url)
    r = Resource(
        submitter_id=user.id,
        name=body.name,
        url=body.url,
        url_normalized=normalized,
        domain=domain,
        description=body.description,
        category_id=cat.id,
        resource_type=body.resource_type,
        official_verified=is_official_domain(domain),
        tags=body.tags,
        level=body.level,
        language=body.language,
        link_status="pending",
        ai_assisted=bool(body.ai_assisted or draft is not None),
        source_draft_id=draft.id if draft else None,
    )
    db.session.add(r)
    try:
        db.session.flush()
    except IntegrityError as e:
        db.session.rollback()
        existing = find_duplicate(normalized)
        raise duplicate(existing.id if existing else "", "This resource is already in the Knowledge Hub.") from e
    # A recommendations draft can publish several resources; claim_draft still accepts published drafts.
    mark_published(draft, "resource", r.id)
    db.session.commit()
    return r


def get_for_owner(resource_id, user) -> Resource:
    r = get_or_404(Resource, resource_id, user, lock=True)
    if r.submitter_id != user.id:
        raise forbidden("Only the submitter can edit this resource.")
    return r


def update_resource(r: Resource, body) -> Resource:
    data = body.model_dump(exclude_unset=True)
    if "url" in data:
        url = data.pop("url")
        _assert_not_blocked(url)
        normalized = normalize_url(url)
        if normalized != r.url_normalized:
            existing = find_duplicate(normalized, exclude_id=r.id)
            if existing is not None:
                raise duplicate(existing.id, "This resource is already in the Knowledge Hub.")
            r.url, r.url_normalized = url, normalized
            r.domain = url_domain(url)
            r.official_verified = is_official_domain(r.domain)
            r.link_status = "pending"
            r.link_http_status = None
            r.link_final_url = None
            r.link_consecutive_failures = 0
            r.link_broken_since = None
        else:
            r.url = url
    if "category" in data:
        r.category_id = category_by_slug("resource", data.pop("category")).id
    if data.pop("ai_assisted", None):
        r.ai_assisted = True
    for k, v in data.items():
        setattr(r, k, v)
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise ApiError("duplicate", "This resource is already in the Knowledge Hub.", 409) from e
    return r


def soft_delete(resource_id, user) -> None:
    r = get_or_404(Resource, resource_id, user, lock=True)
    if r.submitter_id != user.id and not is_mod(user):
        raise forbidden()
    r.deleted_at = datetime.now(UTC)
    db.session.commit()


def run_link_check(r: Resource) -> bool:
    """Synchronous check (recheck endpoint and job). Returns True if the link newly became broken."""
    from app.modules.notifications.service import notify

    result = check_url(r.url)
    became_broken = apply_result(r, result)
    if became_broken:
        notify(r.submitter_id, None, "resource_link_broken", "resource", r, snippet_text=f"{r.url} returned {result.http_status}")
    return became_broken
