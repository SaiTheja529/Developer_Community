from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import created_at_col, enum_check
from app.extensions import db


class Vote(db.Model):
    __tablename__ = "votes"
    __table_args__ = (
        enum_check("target_type", enums.VOTE_TARGETS),
        enum_check("kind", enums.VOTE_KINDS),
        Index("votes_target", "target_type", "target_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    target_type: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    kind: Mapped[str] = mapped_column(Text, primary_key=True, server_default=text("'upvote'"), default="upvote")
    created_at: Mapped[datetime] = created_at_col()


class Bookmark(db.Model):
    __tablename__ = "bookmarks"
    __table_args__ = (
        enum_check("target_type", enums.BOOKMARK_TARGETS),
        Index("bookmarks_target", "target_type", "target_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    target_type: Mapped[str] = mapped_column(Text, primary_key=True)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = created_at_col()
