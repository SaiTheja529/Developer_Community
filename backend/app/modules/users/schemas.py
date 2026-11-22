from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, field_validator

from app.common.pagination import PageParams
from app.common.validation import OptText, OptUrl, QueryModel, StrictModel, Tags, Text, Url


class ContactLink(StrictModel):
    label: Text(1, 40)
    url: Url


class UpdateMeBody(StrictModel):
    username: Text(3, 30) | None = None
    display_name: Text(1, 60) | None = None
    bio: OptText(500) = None
    skills: Tags(15) | None = None
    interests: Tags(15) | None = None
    website_url: OptUrl = None
    github_username: OptText(39) = None
    contact_links: list[ContactLink] | None = Field(default=None, max_length=5)
    contact_visibility: Literal["hidden", "collaborators", "public"] | None = None

    @field_validator("github_username")
    @classmethod
    def _gh(cls, v):
        if v is not None and not re.match(r"^[A-Za-z0-9-]{1,39}$", v):
            raise ValueError("Not a valid GitHub username.")
        return v

    @field_validator("display_name", "skills", "interests", "contact_links", "contact_visibility", "username")
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class CheckUsernameQuery(QueryModel):
    username: str = ""


class ContributionsQuery(PageParams):
    type: Literal["harnesses", "ideas", "resources", "collections", "reviews"] = "harnesses"


class BookmarksQuery(PageParams):
    type: Literal["harness", "idea", "resource", "collection"] | None = None


class MyCollectionsQuery(QueryModel):
    resource_id: str | None = None
