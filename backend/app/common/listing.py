"""Full-text search, filters and sorts shared by list endpoints (spec §11)."""

from __future__ import annotations

from sqlalchemy import Float, Select, cast, extract, func, or_, select

from app.common.errors import bad_request


def fts(model, q: str):
    """Returns (where_clause, rank_expr). Matches websearch_to_tsquery or an exact tag."""
    query = func.websearch_to_tsquery("english", q)
    clause = model.search_vector.op("@@")(query)
    tag = q.strip().lower()
    if tag and hasattr(model, "tags"):
        clause = or_(clause, model.tags.any(tag))
    return clause, func.ts_rank_cd(model.search_vector, query)


def trending_expr(model):
    score = cast(model.vote_count, Float)
    weights = {"comment_count": 0.5, "suggestion_count": 0.5, "review_count": 1.5, "interest_count": 1.0}
    for col, w in weights.items():
        if hasattr(model, col):
            score = score + w * getattr(model, col)
    age_hours = extract("epoch", func.now() - model.created_at) / 3600 + 2
    return score / func.power(age_hours, 1.5)


def sort_columns(model, sort: str) -> list:
    if sort == "recent":
        return [model.created_at.desc()]
    if sort == "popular":
        return [model.vote_count.desc(), model.created_at.desc()]
    if sort == "trending":
        return [trending_expr(model).desc(), model.created_at.desc()]
    if sort == "most_reviewed":
        return [model.review_count.desc(), model.vote_count.desc()]
    if sort == "most_discussed":
        extra = model.suggestion_count if hasattr(model, "suggestion_count") else 0
        return [(model.comment_count + extra).desc(), model.created_at.desc()]
    if sort == "most_interest":
        return [model.interest_count.desc(), model.created_at.desc()]
    raise bad_request(f"Unknown sort '{sort}'.")


def apply_sort(stmt: Select, model, sort: str | None, allowed: list[str], rank=None) -> Select:
    if sort is not None and sort not in allowed:
        raise bad_request(f"Unknown sort '{sort}'. Allowed: {', '.join(allowed)}.")
    if sort is None and rank is not None:
        return stmt.order_by(rank.desc(), model.created_at.desc())
    return stmt.order_by(*sort_columns(model, sort or "recent"))


def tag_list_filter(model, column: str, values: list[str], mode: str = "all"):
    col = getattr(model, column)
    values = [v.strip().lower() for v in values if v.strip()]
    if not values:
        return None
    return col.contains(values) if mode == "all" else col.overlap(values)


def author_filter(model, owner_attr: str, username: str):
    from app.modules.users.models import User

    sub = select(User.id).where(User.username == username).scalar_subquery()
    return getattr(model, owner_attr) == sub


def category_filter(model, module: str, slug: str):
    from app.modules.meta.models import Category

    sub = select(Category.id).where(Category.module == module, Category.slug == slug).scalar_subquery()
    return model.category_id == sub
