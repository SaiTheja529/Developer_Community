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
    status_col,
    text_array,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db


class Resource(db.Model):
    __tablename__ = "resources"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        enum_check("resource_type", enums.RESOURCE_TYPES),
        enum_check("level", enums.RESOURCE_LEVELS, nullable=True),
        enum_check("link_status", enums.LINK_STATUSES),
        Index("resources_url_unique", "url_normalized", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("resources_search", "search_vector", postgresql_using="gin"),
        Index("resources_tags", "tags", postgresql_using="gin"),
        Index("resources_category", "category_id"),
        Index("resources_type", "resource_type"),
        Index("resources_link_status", "link_status"),
        Index("resources_created", text("created_at DESC")),
        Index("resources_votes", text("vote_count DESC")),
        Index("resources_submitter", "submitter_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    submitter_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_normalized: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    official_verified: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    tags: Mapped[list[str]] = text_array()
    level: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    link_status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    link_http_status: Mapped[int | None] = mapped_column()
    link_final_url: Mapped[str | None] = mapped_column(Text)
    link_last_checked_at: Mapped[datetime | None] = tstz()
    link_consecutive_failures: Mapped[int] = counter()
    # Addition to the spec DDL: when the link became broken/unreachable (for the 7-day listing rule, §8.6).
    link_broken_since: Mapped[datetime | None] = tstz()
    broken_report_count: Mapped[int] = counter()
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    source_draft_id: Mapped[uuid.UUID | None] = fk_uuid("ai_drafts.id", nullable=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = status_col()
    vote_count: Mapped[int] = counter()
    comment_count: Mapped[int] = counter()
    suggestion_count: Mapped[int] = counter()
    bookmark_count: Mapped[int] = counter()
    collection_count: Mapped[int] = counter()
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(name,'')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description,'')), 'B')",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "submitter_id"
