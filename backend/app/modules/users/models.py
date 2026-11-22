from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, Text, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import (
    created_at_col,
    enum_check,
    jsonb_list,
    text_array,
    tstz,
    updated_at_col,
    uuid_pk,
)
from app.extensions import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        enum_check("contact_visibility", enums.CONTACT_VISIBILITY),
        enum_check("role", enums.ROLES),
        enum_check("status", enums.USER_STATUSES),
        Index("users_username_trgm", "username", postgresql_using="gin", postgresql_ops={"username": "gin_trgm_ops"}),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str | None] = mapped_column(CITEXT, unique=True)
    email_verified_at: Mapped[datetime | None] = tstz()
    password_hash: Mapped[str | None] = mapped_column(Text)
    password_changed_at: Mapped[datetime | None] = tstz()
    failed_login_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"), default=0)
    # Addition to the spec DDL: start of the 15-minute failed-login window (§6.4).
    last_failed_login_at: Mapped[datetime | None] = tstz()
    locked_until: Mapped[datetime | None] = tstz()
    last_login_at: Mapped[datetime | None] = tstz()
    username: Mapped[str] = mapped_column(CITEXT, nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    bio: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = text_array()
    interests: Mapped[list[str]] = text_array()
    website_url: Mapped[str | None] = mapped_column(Text)
    github_username: Mapped[str | None] = mapped_column(Text)
    contact_links: Mapped[list] = jsonb_list()
    contact_visibility: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'hidden'"), default="hidden")
    role: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'user'"), default="user")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'active'"), default="active")
    last_seen_at: Mapped[datetime | None] = tstz()
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()

    @property
    def is_moderator(self) -> bool:
        return self.role in ("moderator", "admin")

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def email_verified(self) -> bool:
        return self.email_verified_at is not None
