from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Index, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import (
    counter,
    created_at_col,
    enum_check,
    fk_uuid,
    jsonb_list,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db


class AIConversation(db.Model):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        enum_check("context_type", enums.AI_CONTEXT_TYPES, nullable=True),
        Index(
            "ai_conversations_user",
            "user_id",
            text("last_message_at DESC NULLS LAST"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    title: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'New conversation'"), default="New conversation"
    )
    context_type: Mapped[str | None] = mapped_column(Text)
    context_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    message_count: Mapped[int] = counter()
    last_message_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = tstz()


class AIMessage(db.Model):
    __tablename__ = "ai_messages"
    __table_args__ = (
        enum_check("role", ["user", "assistant"]),
        enum_check("status", enums.AI_MESSAGE_STATUSES),
        Index("ai_messages_conv", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    conversation_id: Mapped[uuid.UUID] = fk_uuid("ai_conversations.id")
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'complete'"), default="complete")
    context_sources: Mapped[list] = jsonb_list()
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column()
    output_tokens: Mapped[int | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()


class AIDraft(db.Model):
    __tablename__ = "ai_drafts"
    __table_args__ = (
        enum_check("task", enums.AI_DRAFT_TASKS),
        enum_check("status", enums.AI_DRAFT_STATUSES),
        Index("ai_drafts_user", "user_id", text("updated_at DESC")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    task: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, nullable=False)
    context_sources: Mapped[list] = jsonb_list()
    history: Mapped[list] = jsonb_list()
    revision: Mapped[int] = mapped_column(nullable=False, server_default=text("1"), default=1)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'draft'"), default="draft")
    published_target_type: Mapped[str | None] = mapped_column(Text)
    published_target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    model: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()


class AIUsage(db.Model):
    __tablename__ = "ai_usage"
    __table_args__ = (
        enum_check("outcome", enums.AI_USAGE_OUTCOMES),
        Index("ai_usage_user_day", "user_id", "created_at"),
        Index("ai_usage_created", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID | None] = fk_uuid("users.id", nullable=True)
    feature: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    input_tokens: Mapped[int] = counter()
    cached_input_tokens: Mapped[int] = counter()
    output_tokens: Mapped[int] = counter()
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False, server_default=text("0"), default=0
    )
    latency_ms: Mapped[int | None] = mapped_column()
    outcome: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
