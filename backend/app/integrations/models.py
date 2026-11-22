from __future__ import annotations

from datetime import datetime

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.common.db import created_at_col, enum_check
from app.extensions import db


class GithubRepoCache(db.Model):
    __tablename__ = "github_repo_cache"
    __table_args__ = (enum_check("fetch_status", ["ok", "not_found", "private", "error", "rate_limited"]),)

    owner: Mapped[str] = mapped_column(Text, primary_key=True)  # lowercase
    repo: Mapped[str] = mapped_column(Text, primary_key=True)  # lowercase
    fetch_status: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    readme: Mapped[str | None] = mapped_column(Text)
    tree: Mapped[list | None] = mapped_column(JSONB)
    key_files: Mapped[dict | None] = mapped_column(JSONB)
    etag: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = created_at_col()
