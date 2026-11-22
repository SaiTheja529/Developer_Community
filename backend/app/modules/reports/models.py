from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import created_at_col, enum_check, fk_uuid, tstz, uuid_pk
from app.extensions import db


class Report(db.Model):
    __tablename__ = "reports"
    __table_args__ = (
        enum_check("target_type", enums.REPORT_TARGETS),
        enum_check("reason", enums.REPORT_REASONS),
        enum_check("status", enums.REPORT_STATUSES),
        Index(
            "reports_one_open",
            "reporter_id",
            "target_type",
            "target_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
        ),
        Index("reports_queue", "status", "created_at"),
        Index("reports_target", "target_type", "target_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    reporter_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'open'"), default="open")
    resolved_by: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()


class ModerationAction(db.Model):
    """Append-only audit log."""

    __tablename__ = "moderation_actions"
    __table_args__ = (Index("moderation_actions_created", text("created_at DESC")),)

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    # The column is named "metadata" in the spec; SQLAlchemy reserves that attribute name.
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict
    )
    created_at: Mapped[datetime] = created_at_col()
