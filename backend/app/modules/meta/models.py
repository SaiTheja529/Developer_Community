from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.common import enums
from app.common.db import created_at_col, enum_check
from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"
    __table_args__ = (enum_check("module", enums.CATEGORY_MODULES), UniqueConstraint("module", "slug", name="module_slug"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(nullable=False, server_default=text("0"), default=0)
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"), default=True)

    def to_dict(self) -> dict:
        return {"slug": self.slug, "name": self.name}


class TrustedDomain(db.Model):
    __tablename__ = "trusted_domains"
    __table_args__ = (enum_check("kind", enums.TRUSTED_DOMAIN_KINDS),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    added_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = created_at_col()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "domain": self.domain,
            "kind": self.kind,
            "label": self.label,
            "created_at": self.created_at,
        }
