"""/api/collections endpoints (spec §8.7)."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, g
from pydantic import Field, field_validator

from app.auth.decorators import optional_auth, require_auth, require_verified
from app.common.content import get_or_404
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import creation_limit, limit
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import (
    CsvList,
    OptText,
    QueryBool,
    StrictModel,
    Tags,
    Text,
    parse_body,
    validate_query,
)
from app.modules.collections import service
from app.modules.collections.models import Collection

bp = Blueprint("collections", __name__, url_prefix="/api/collections")


class ItemIn(StrictModel):
    resource_id: uuid.UUID
    note: OptText(500) = None


class CollectionCreate(StrictModel):
    title: Text(3, 120)
    description: OptText(5000) = None
    category: str
    tags: Tags(8) = Field(default_factory=list)
    visibility: Literal["public", "private"] = "public"
    items: list[ItemIn] | None = Field(default=None, max_length=100)
    source_draft_id: uuid.UUID | None = None
    ai_assisted: bool = False


class CollectionUpdate(StrictModel):
    title: Text(3, 120) | None = None
    description: OptText(5000) = None
    category: str | None = None
    tags: Tags(8) | None = None
    visibility: Literal["public", "private"] | None = None
    ai_assisted: bool | None = None

    @field_validator("title", "category", "tags", "visibility")
    @classmethod
    def _not_null(cls, v, info):
        if v is None:
            raise ValueError(f"{info.field_name} cannot be null.")
        return v


class AddItem(StrictModel):
    resource_id: uuid.UUID
    note: OptText(500) = None
    position: int | None = Field(default=None, ge=0)


class UpdateItem(StrictModel):
    note: OptText(500) = None


class ReorderBody(StrictModel):
    resource_ids: list[uuid.UUID] = Field(max_length=100)


class CollectionListQuery(PageParams):
    q: str | None = None
    category: str | None = None
    tags: CsvList = Field(default_factory=list)
    author: str | None = None
    featured: QueryBool = False
    sort: str | None = None


@bp.get("")
@optional_auth
@validate_query(CollectionListQuery)
def list_collections(query: CollectionListQuery):
    page = paginate(service.list_collections(query, g.current_user), query.page, query.page_size)
    return paginated(service.summaries(page.items, g.current_user), page.page, page.page_size, page.total)


@bp.post("")
@require_auth
@require_verified
@limit(creation_limit, "create_collection")
def create_collection():
    body = parse_body(CollectionCreate)
    c = service.create(g.current_user, body)
    return created(service.detail(c, g.current_user))


@bp.get("/<uuid:collection_id>")
@optional_auth
def get_collection(collection_id: uuid.UUID):
    return ok(service.detail(get_or_404(Collection, collection_id, g.current_user), g.current_user))


@bp.patch("/<uuid:collection_id>")
@require_auth
@require_verified
def update_collection(collection_id: uuid.UUID):
    body = parse_body(CollectionUpdate)
    c = service.update_collection(service.get_for_owner(collection_id, g.current_user), body)
    return ok(service.detail(c, g.current_user))


@bp.delete("/<uuid:collection_id>")
@require_auth
@require_verified
def delete_collection(collection_id: uuid.UUID):
    service.soft_delete(collection_id, g.current_user)
    return no_content()


@bp.post("/<uuid:collection_id>/items")
@require_auth
@require_verified
def add_item(collection_id: uuid.UUID):
    body = parse_body(AddItem)
    c = service.get_for_owner(collection_id, g.current_user)
    service.add_item(c, g.current_user, body)
    return created(service.detail(c, g.current_user))


@bp.put("/<uuid:collection_id>/items/order")
@require_auth
@require_verified
def reorder_items(collection_id: uuid.UUID):
    body = parse_body(ReorderBody)
    c = service.get_for_owner(collection_id, g.current_user)
    service.reorder(c, body.resource_ids)
    return ok(service.detail(c, g.current_user))


@bp.patch("/<uuid:collection_id>/items/<uuid:resource_id>")
@require_auth
@require_verified
def update_item(collection_id: uuid.UUID, resource_id: uuid.UUID):
    body = parse_body(UpdateItem)
    c = service.get_for_owner(collection_id, g.current_user)
    service.update_item(c, resource_id, body.note)
    return ok(service.detail(c, g.current_user))


@bp.delete("/<uuid:collection_id>/items/<uuid:resource_id>")
@require_auth
@require_verified
def remove_item(collection_id: uuid.UUID, resource_id: uuid.UUID):
    c = service.get_for_owner(collection_id, g.current_user)
    service.remove_item(c, resource_id)
    return no_content()
