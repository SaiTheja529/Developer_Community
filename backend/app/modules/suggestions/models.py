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
    jsonb_dict,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db


class Suggestion(db.Model):
    __tablename__ = "suggestions"
    __table_args__ = (
        enum_check("status", enums.SUGGESTION_STATUSES),
        enum_check("moderation_status", enums.CONTENT_STATUSES),
        CheckConstraint("num_nonnulls(harness_id, idea_id, resource_id) = 1", name="one_target"),
        Index("suggestions_harness", "harness_id", "created_at", postgresql_where=text("harness_id IS NOT NULL")),
        Index("suggestions_idea", "idea_id", "created_at", postgresql_where=text("idea_id IS NOT NULL")),
        Index("suggestions_resource", "resource_id", "created_at", postgresql_where=text("resource_id IS NOT NULL")),
        Index("suggestions_author", "author_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    author_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    harness_id: Mapped[uuid.UUID | None] = fk_uuid("harnesses.id", nullable=True)
    idea_id: Mapped[uuid.UUID | None] = fk_uuid("ideas.id", nullable=True)
    resource_id: Mapped[uuid.UUID | None] = fk_uuid("resources.id", nullable=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = jsonb_dict()
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"), default="open")
    owner_response: Mapped[str | None] = mapped_column(Text)
    status_changed_at: Mapped[datetime | None] = tstz()
    ai_assisted: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    vote_count: Mapped[int] = counter()
    moderation_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'published'"), default="published"
    )
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()

    owner_attr = "author_id"
    status_attr = "moderation_status"

    @property
    def target(self) -> tuple[str, uuid.UUID]:
        for t in ("harness", "idea", "resource"):
            v = getattr(self, f"{t}_id")
            if v is not None:
                return t, v
        raise ValueError("suggestion without target")
