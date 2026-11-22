from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field, field_validator

from app.common import enums
from app.common.pagination import PageParams
from app.common.validation import CsvList, OptText, QueryBool, StrictModel, Tags, Text

ToolName = Literal[tuple(enums.TOOLS)]  # type: ignore[valid-type]
ComponentType = Literal[tuple(enums.COMPONENT_TYPES)]  # type: ignore[valid-type]


class ComponentIn(StrictModel):
    type: ComponentType
    name: Text(1, 100)
    description: OptText(2000) = None


def _dedupe(v):
    if v is None:
        return v
    out = []
    for x in v:
        if x not in out:
            out.append(x)
    return out


class HarnessCreate(StrictModel):
    name: Text(3, 100)
    repo_url: Text(1, 2048)
    short_description: Text(20, 280)
    detailed_explanation: Text(50, 20000)
    architecture: OptText(20000) = None
    components: list[ComponentIn] = Field(default_factory=list, max_length=50)
    setup_instructions: OptText(20000) = None
    limitations: OptText(10000) = None
    tools: list[ToolName] = Field(min_length=1, max_length=10)
    category: str
    tags: Tags(8) = Field(default_factory=list)
    accepts_collaboration: bool = False
    source_draft_id: uuid.UUID | None = None
    ai_assisted: bool = False

    @field_validator("tools")
    @classmethod
    def _dedupe_tools(cls, v):
        return _dedupe(v)


class HarnessUpdate(StrictModel):
    name: Text(3, 100) | None = None
    repo_url: Text(1, 2048) | None = None
    short_description: Text(20, 280) | None = None
    detailed_explanation: Text(50, 20000) | None = None
    architecture: OptText(20000) = None
    components: list[ComponentIn] | None = Field(default=None, max_length=50)
    setup_instructions: OptText(20000) = None
    limitations: OptText(10000) = None
    tools: list[ToolName] | None = Field(default=None, min_length=1, max_length=10)
    category: str | None = None
    tags: Tags(8) | None = None
    accepts_collaboration: bool | None = None
    ai_assisted: bool | None = None

    @field_validator("tools")
    @classmethod
    def _dedupe_tools(cls, v):
        return _dedupe(v)

    @field_validator(
        "name", "repo_url", "short_description", "detailed_explanation", "components", "tools", "category", "tags",
        "accepts_collaboration",
    )
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class HarnessListQuery(PageParams):
    q: str | None = None
    category: str | None = None
    tags: CsvList = Field(default_factory=list)
    tools: CsvList = Field(default_factory=list)
    author: str | None = None
    featured: QueryBool = False
    sort: str | None = None


class Ratings(StrictModel):
    documentation: int | None = Field(default=None, ge=1, le=5)
    setup: int | None = Field(default=None, ge=1, le=5)
    coordination: int | None = Field(default=None, ge=1, le=5)
    reliability: int | None = Field(default=None, ge=1, le=5)
    overall: int | None = Field(default=None, ge=1, le=5)


class ReviewCreate(StrictModel):
    what_tested: Text(20, 5000)
    worked_well: OptText(5000) = None
    did_not_work: OptText(5000) = None
    recommendations: OptText(5000) = None
    environment: OptText(500) = None
    ratings: Ratings = Field(default_factory=Ratings)


class ReviewUpdate(StrictModel):
    what_tested: Text(20, 5000) | None = None
    worked_well: OptText(5000) = None
    did_not_work: OptText(5000) = None
    recommendations: OptText(5000) = None
    environment: OptText(500) = None
    ratings: Ratings | None = None


class ReviewListQuery(PageParams):
    sort: Literal["helpful", "recent"] = "helpful"
