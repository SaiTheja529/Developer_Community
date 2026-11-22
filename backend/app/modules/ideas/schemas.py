from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field, field_validator

from app.common.pagination import PageParams
from app.common.validation import CsvList, OptText, OptUrl, QueryBool, StrictModel, Tags, Text

CollabStatus = Literal["sharing", "seeking_collaborators", "team_formed"]


class FeatureIn(StrictModel):
    title: Text(1, 150)
    detail: OptText(2000) = None


def _github_url(v):
    if v is None:
        return v
    from urllib.parse import urlsplit

    host = (urlsplit(v).hostname or "").lower()
    if host not in ("github.com", "www.github.com"):
        raise ValueError("Must be a GitHub URL.")
    return v


class IdeaCreate(StrictModel):
    title: Text(5, 120)
    problem_statement: Text(20, 5000)
    proposed_solution: Text(20, 5000)
    description: OptText(20000) = None
    tech_stack: Tags(20) = Field(default_factory=list)
    expected_features: list[FeatureIn] = Field(default_factory=list, max_length=30)
    category: str
    tags: Tags(8) = Field(default_factory=list)
    github_url: OptUrl = None
    collaboration_status: CollabStatus = "sharing"
    source_draft_id: uuid.UUID | None = None
    ai_assisted: bool = False

    @field_validator("github_url")
    @classmethod
    def _gh(cls, v):
        return _github_url(v)


class IdeaUpdate(StrictModel):
    title: Text(5, 120) | None = None
    problem_statement: Text(20, 5000) | None = None
    proposed_solution: Text(20, 5000) | None = None
    description: OptText(20000) = None
    tech_stack: Tags(20) | None = None
    expected_features: list[FeatureIn] | None = Field(default=None, max_length=30)
    category: str | None = None
    tags: Tags(8) | None = None
    github_url: OptUrl = None
    collaboration_status: CollabStatus | None = None
    ai_assisted: bool | None = None

    @field_validator("github_url")
    @classmethod
    def _gh(cls, v):
        return _github_url(v)

    @field_validator(
        "title", "problem_statement", "proposed_solution", "tech_stack", "expected_features", "category", "tags",
        "collaboration_status",
    )
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class IdeaListQuery(PageParams):
    q: str | None = None
    category: str | None = None
    tags: CsvList = Field(default_factory=list)
    tech: CsvList = Field(default_factory=list)
    author: str | None = None
    collaboration_status: CollabStatus | None = None
    featured: QueryBool = False
    sort: str | None = None
