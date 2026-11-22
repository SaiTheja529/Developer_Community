from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Computed, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR
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


class Idea(db.Model):
    __tablename__ = "ideas"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        enum_check("collaboration_status", enums.COLLABORATION_STATUSES),
        Index("ideas_search", "search_vector", postgresql_using="gin"),
        Index("ideas_tags", "tags", postgresql_using="gin"),
        Index("ideas_tech_stack", "tech_stack", postgresql_using="gin"),
        Index("ideas_created", text("created_at DESC"), postgresql_where=_PUBLISHED),
        Index("ideas_votes", text("vote_count DESC"), postgresql_where=_PUBLISHED),
        Index("ideas_author", "author_id"),
        Index("ideas_category", "category_id"),
        Index("ideas_collab_status", "collaboration_status", postgresql_where=text("deleted_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tech_stack: Mapped[list[str]] = text_array()
    expected_features: Mapped[list] = jsonb_list()
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    tags: Mapped[list[str]] = text_array()
    github_url: Mapped[str | None] = mapped_column(Text)
    collaboration_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'sharing'"), default="sharing"
    )
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    source_draft_id: Mapped[uuid.UUID | None] = fk_uuid("ai_drafts.id", nullable=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = status_col()
    vote_count: Mapped[int] = counter()
    interest_count: Mapped[int] = counter()
    comment_count: Mapped[int] = counter()
    suggestion_count: Mapped[int] = counter()
    collaborator_count: Mapped[int] = counter()
    bookmark_count: Mapped[int] = counter()
    last_activity_at: Mapped[datetime] = created_at_col()
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('english', coalesce(problem_statement,'')), 'B') || "
            "setweight(to_tsvector('english', coalesce(proposed_solution,'')), 'B') || "
            "setweight(to_tsvector('english', coalesce(description,'')), 'C')",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "author_id"
