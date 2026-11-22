"""Shared column helpers for SQLAlchemy models (spec §7.1)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def created_at_col() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now())


def updated_at_col() -> Mapped[datetime]:
    return mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), default=func.now(), onupdate=func.now()
    )


def tstz(nullable: bool = True, **kw) -> Mapped[datetime | None]:
    return mapped_column(DateTime(timezone=True), nullable=nullable, **kw)


def text_array() -> Mapped[list[str]]:
    return mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"), default=list)


def jsonb_list() -> Mapped[list]:
    return mapped_column(JSONB, nullable=False, server_default=text("'[]'::jsonb"), default=list)


def jsonb_dict() -> Mapped[dict]:
    return mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"), default=dict)


def counter() -> Mapped[int]:
    return mapped_column(nullable=False, server_default=text("0"), default=0)


def enum_check(column: str, values: list[str], name: str | None = None, nullable: bool = False) -> CheckConstraint:
    quoted = ",".join(f"'{v}'" for v in values)
    expr = f"{column} IN ({quoted})"
    if nullable:
        expr = f"{column} IS NULL OR {expr}"
    return CheckConstraint(expr, name=name or column)


def status_col() -> Mapped[str]:
    return mapped_column(Text, nullable=False, server_default=text("'published'"), default="published")


def fk_uuid(target: str, nullable: bool = False, index: bool = False):
    from sqlalchemy import ForeignKey

    return mapped_column(UUID(as_uuid=True), ForeignKey(target), nullable=nullable, index=index)
