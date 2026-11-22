from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field, field_validator

from app.common import enums
from app.common.pagination import PageParams
from app.common.validation import CsvList, QueryBool, QueryModel, StrictModel, Tags, Text, Url

ResourceType = Literal[tuple(enums.RESOURCE_TYPES)]  # type: ignore[valid-type]
Level = Literal["beginner", "intermediate", "advanced"]


def _lang(v):
    if v is None:
        return v
    v = v.strip().lower()
    if len(v) != 2 or not v.isalpha():
        raise ValueError("Use a 2-letter ISO 639-1 code, e.g. 'en'.")
    return v


class ResourceCreate(StrictModel):
    name: Text(3, 150)
    url: Url
    description: Text(20, 3000)
    category: str
    resource_type: ResourceType
    tags: Tags(8) = Field(default_factory=list)
    level: Level | None = None
    language: str | None = None
    source_draft_id: uuid.UUID | None = None
    ai_assisted: bool = False

    @field_validator("language")
    @classmethod
    def _language(cls, v):
        return _lang(v)


class ResourceUpdate(StrictModel):
    name: Text(3, 150) | None = None
    url: Url | None = None
    description: Text(20, 3000) | None = None
    category: str | None = None
    resource_type: ResourceType | None = None
    tags: Tags(8) | None = None
    level: Level | None = None
    language: str | None = None
    ai_assisted: bool | None = None

    @field_validator("language")
    @classmethod
    def _language(cls, v):
        return _lang(v)

    @field_validator("name", "url", "description", "category", "resource_type", "tags")
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class ResourceListQuery(PageParams):
    q: str | None = None
    category: str | None = None
    tags: CsvList = Field(default_factory=list)
    resource_type: ResourceType | None = None
    level: Level | None = None
    language: str | None = None
    official: QueryBool = False
    domain: str | None = None
    author: str | None = None
    link_status: Literal[tuple(enums.LINK_STATUSES)] | None = None  # type: ignore[valid-type]
    include_broken: QueryBool = False
    featured: QueryBool = False
    sort: str | None = None


class CheckUrlQuery(QueryModel):
    url: str = ""
