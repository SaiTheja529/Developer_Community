from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import created_at_col, enum_check, fk_uuid, text_array, tstz, updated_at_col, uuid_pk
from app.extensions import db


class CollaborationRequest(db.Model):
    __tablename__ = "collaboration_requests"
    __table_args__ = (
        enum_check("status", enums.COLLAB_STATUSES),
        CheckConstraint("num_nonnulls(idea_id, harness_id) = 1", name="one_target"),
        Index(
            "collab_one_pending_idea",
            "idea_id",
            "requester_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND idea_id IS NOT NULL"),
        ),
        Index(
            "collab_one_pending_harness",
            "harness_id",
            "requester_id",
            unique=True,
            postgresql_where=text("status = 'pending' AND harness_id IS NOT NULL"),
        ),
        Index("collab_owner", "owner_id", "status", text("created_at DESC")),
        Index("collab_requester", "requester_id", "status", text("created_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    idea_id: Mapped[uuid.UUID | None] = fk_uuid("ideas.id", nullable=True)
    harness_id: Mapped[uuid.UUID | None] = fk_uuid("harnesses.id", nullable=True)
    requester_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    owner_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    skills: Mapped[list[str]] = text_array()
    requester_shares_contact: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    owner_shares_contact: Mapped[bool] = mapped_column(nullable=False, server_default=text("false"), default=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"), default="pending")
    response_message: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    @property
    def target(self) -> tuple[str, uuid.UUID]:
        if self.idea_id is not None:
            return "idea", self.idea_id
        return "harness", self.harness_id  # type: ignore[return-value]
