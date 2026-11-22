from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Computed, ForeignKey, Index, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import (
    counter,
    created_at_col,
    enum_check,
    fk_uuid,
    jsonb_list,
    status_col,
    text_array,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db

_PUBLISHED = text("deleted_at IS NULL AND status = 'published'")


class Harness(db.Model):
    __tablename__ = "harnesses"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        Index(
            "harnesses_repo_unique",
            text("lower(repo_owner)"),
            text("lower(repo_name)"),
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("harnesses_search", "search_vector", postgresql_using="gin"),
        Index("harnesses_tags", "tags", postgresql_using="gin"),
        Index("harnesses_tools", "tools", postgresql_using="gin"),
        Index("harnesses_created", text("created_at DESC"), postgresql_where=_PUBLISHED),
        Index("harnesses_votes", text("vote_count DESC"), postgresql_where=_PUBLISHED),
        Index("harnesses_author", "author_id"),
        Index("harnesses_category", "category_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    repo_url: Mapped[str] = mapped_column(Text, nullable=False)
    repo_owner: Mapped[str] = mapped_column(Text, nullable=False)
    repo_name: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[str] = mapped_column(Text, nullable=False)
    detailed_explanation: Mapped[str] = mapped_column(Text, nullable=False)
    architecture: Mapped[str | None] = mapped_column(Text)
    components: Mapped[list] = jsonb_list()
    setup_instructions: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    tools: Mapped[list[str]] = text_array()
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    tags: Mapped[list[str]] = text_array()
    accepts_collaboration: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    repo_metadata: Mapped[dict | None] = mapped_column(JSONB)
    repo_metadata_fetched_at: Mapped[datetime | None] = tstz()
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    source_draft_id: Mapped[uuid.UUID | None] = fk_uuid("ai_drafts.id", nullable=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = status_col()
    vote_count: Mapped[int] = counter()
    comment_count: Mapped[int] = counter()
    suggestion_count: Mapped[int] = counter()
    review_count: Mapped[int] = counter()
    bookmark_count: Mapped[int] = counter()
    last_activity_at: Mapped[datetime] = created_at_col()
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(name,'')), 'A') || "
            "setweight(to_tsvector('english', coalesce(short_description,'')), 'B') || "
            "setweight(to_tsvector('english', coalesce(detailed_explanation,'')), 'C')",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "author_id"


def _rating(name: str) -> CheckConstraint:
    return CheckConstraint(f"{name} BETWEEN 1 AND 5", name=name)


class HarnessReview(db.Model):
    __tablename__ = "harness_reviews"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        _rating("rating_documentation"),
        _rating("rating_setup"),
        _rating("rating_coordination"),
        _rating("rating_reliability"),
        _rating("rating_overall"),
        Index(
            "harness_reviews_one_per_user",
            "harness_id",
            "author_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("harness_reviews_harness", "harness_id", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    harness_id: Mapped[uuid.UUID] = fk_uuid("harnesses.id")
    author_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    what_tested: Mapped[str] = mapped_column(Text, nullable=False)
    worked_well: Mapped[str | None] = mapped_column(Text)
    did_not_work: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[str | None] = mapped_column(Text)
    rating_documentation: Mapped[int | None] = mapped_column(SmallInteger)
    rating_setup: Mapped[int | None] = mapped_column(SmallInteger)
    rating_coordination: Mapped[int | None] = mapped_column(SmallInteger)
    rating_reliability: Mapped[int | None] = mapped_column(SmallInteger)
    rating_overall: Mapped[int | None] = mapped_column(SmallInteger)
    vote_count: Mapped[int] = counter()
    status: Mapped[str] = status_col()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "author_id"
