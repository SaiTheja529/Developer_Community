from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import created_at_col, enum_check, fk_uuid, tstz, uuid_pk
from app.extensions import db


class AuthSession(db.Model):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        enum_check("revoked_reason", enums.SESSION_REVOKE_REASONS, nullable=True),
        Index("auth_sessions_user", "user_id", postgresql_where=text("revoked_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    previous_token_hash: Mapped[str | None] = mapped_column(Text, unique=True)
    rotated_at: Mapped[datetime | None] = tstz()
    user_agent: Mapped[str | None] = mapped_column(Text)
    device_label: Mapped[str | None] = mapped_column(Text)
    ip_prefix: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    last_used_at: Mapped[datetime] = created_at_col()
    expires_at: Mapped[datetime] = tstz(nullable=False)
    absolute_expires_at: Mapped[datetime] = tstz(nullable=False)
    revoked_at: Mapped[datetime | None] = tstz()
    revoked_reason: Mapped[str | None] = mapped_column(Text)


class EmailToken(db.Model):
    __tablename__ = "email_tokens"
    __table_args__ = (
        enum_check("purpose", enums.EMAIL_TOKEN_PURPOSES),
        Index("email_tokens_user_purpose", "user_id", "purpose", postgresql_where=text("used_at IS NULL")),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = fk_uuid("users.id")
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    new_email: Mapped[str | None] = mapped_column(CITEXT)
    expires_at: Mapped[datetime] = tstz(nullable=False)
    used_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()


class OAuthAccount(db.Model):
    """A GitHub or Google identity linked to a DevCommons user (addition to the spec).

    Matching on later sign-ins uses (provider, provider_user_id), never the email, so a changed
    email at the provider can't move the identity to another account.
    """

    __tablename__ = "oauth_accounts"
    __table_args__ = (
        enum_check("provider", enums.OAUTH_PROVIDERS),
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_accounts_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_oauth_accounts_user_provider"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(CITEXT)
    login: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()
    last_used_at: Mapped[datetime] = created_at_col()
