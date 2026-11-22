from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import created_at_col, fk_uuid, jsonb_dict, tstz, uuid_pk
from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("notifications_inbox", "recipient_id", text("created_at DESC")),
        Index("notifications_unread", "recipient_id", postgresql_where=text("read_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    recipient_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    actor_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    data: Mapped[dict] = jsonb_dict()
    read_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()
