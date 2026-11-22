from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import (
    counter,
    created_at_col,
    enum_check,
    fk_uuid,
    status_col,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db


class Comment(db.Model):
    __tablename__ = "comments"
    __table_args__ = (
        enum_check("status", enums.CONTENT_STATUSES),
        CheckConstraint("num_nonnulls(harness_id, idea_id, resource_id, collection_id) = 1", name="one_target"),
        Index("comments_harness", "harness_id", "created_at", postgresql_where=text("harness_id IS NOT NULL")),
        Index("comments_idea", "idea_id", "created_at", postgresql_where=text("idea_id IS NOT NULL")),
        Index("comments_resource", "resource_id", "created_at", postgresql_where=text("resource_id IS NOT NULL")),
        Index("comments_collection", "collection_id", "created_at", postgresql_where=text("collection_id IS NOT NULL")),
        Index("comments_parent", "parent_id", "created_at"),
        Index("comments_author", "author_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    author_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    harness_id: Mapped[uuid.UUID | None] = fk_uuid("harnesses.id", nullable=True)
    idea_id: Mapped[uuid.UUID | None] = fk_uuid("ideas.id", nullable=True)
    resource_id: Mapped[uuid.UUID | None] = fk_uuid("resources.id", nullable=True)
    collection_id: Mapped[uuid.UUID | None] = fk_uuid("collections.id", nullable=True)
    parent_id: Mapped[uuid.UUID | None] = fk_uuid("comments.id", nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    vote_count: Mapped[int] = counter()
    reply_count: Mapped[int] = counter()
    status: Mapped[str] = status_col()
    edited_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "author_id"

    @property
    def target(self) -> tuple[str, uuid.UUID]:
        for t in ("harness", "idea", "resource", "collection"):
            v = getattr(self, f"{t}_id")
            if v is not None:
                return t, v
        raise ValueError("comment without target")
