"""Offset pagination with a total count (spec §5.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Select, func, select

from app.extensions import db


class PageParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    page: int = Field(1, ge=1, le=100_000)
    page_size: int = Field(20, ge=1, le=50)


@dataclass
class Page:
    items: list[Any]
    page: int
    page_size: int
    total: int


def paginate(stmt: Select, page: int, page_size: int, scalars: bool = True) -> Page:
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = db.session.execute(count_stmt).scalar_one()
    paged = stmt.limit(page_size).offset((page - 1) * page_size)
    result = db.session.execute(paged)
    items = list(result.scalars().all()) if scalars else list(result.all())
    return Page(items=items, page=page, page_size=page_size, total=total)
