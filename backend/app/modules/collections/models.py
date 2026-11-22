from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Computed, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
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


class Collection(db.Model):
    __tablename__ = "collections"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        enum_check("visibility", enums.COLLECTION_VISIBILITY),
        Index("collections_search", "search_vector", postgresql_using="gin"),
        Index("collections_tags", "tags", postgresql_using="gin"),
        Index("collections_owner", "owner_id"),
        Index("collections_created", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    owner_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    tags: Mapped[list[str]] = text_array()
    visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'public'"), default="public")
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    source_draft_id: Mapped[uuid.UUID | None] = fk_uuid("ai_drafts.id", nullable=True)
    is_featured: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = status_col()
    item_count: Mapped[int] = counter()
    vote_count: Mapped[int] = counter()
    comment_count: Mapped[int] = counter()
    bookmark_count: Mapped[int] = counter()
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('english', coalesce(title,'')), 'A') || "
            "setweight(to_tsvector('english', coalesce(description,'')), 'B')",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "owner_id"


class CollectionItem(db.Model):
    __tablename__ = "collection_items"
    __table_args__ = (Index("collection_items_order", "collection_id", "position"),)

    collection_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("collections.id"), primary_key=True)
    resource_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("resources.id"), primary_key=True)
    position: Mapped[int] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = created_at_col()
