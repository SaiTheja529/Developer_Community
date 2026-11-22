"""Shared suggestions for harnesses, ideas and resources (spec §8.9)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import and_, or_, select

from app.common import enums
from app.common.content import (
    can_view,
    get_or_404,
    is_mod,
    load_users,
    model_for,
    owner_id_of,
    user_summary,
    viewer_states,
)
from app.common.counters import bump
from app.common.errors import bad_request, forbidden, not_found, pydantic_fields, validation_error
from app.common.text import normalize_tags, validate_http_url
from app.extensions import db
from app.modules.notifications.service import notify
from app.modules.suggestions.models import Suggestion

# Kind-specific payloads ------------------------------------------------------------------


class _Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComponentRecommendation(_Payload):
    component_type: str = Field(pattern="^(" + "|".join(enums.COMPONENT_TYPES) + ")$")
    component_name: str = Field(min_length=1, max_length=100)


class TechStack(_Payload):
    technologies: list[str] = Field(min_length=1, max_length=20)


class AlternativeResource(_Payload):
    resource_id: uuid.UUID | None = None
    url: str | None = None


PAYLOAD_MODELS = {
    "component_recommendation": ComponentRecommendation,
    "tech_stack": TechStack,
    "alternative_resource": AlternativeResource,
}


def validate_payload(kind: str, payload: dict | None) -> dict:
    payload = payload or {}
    model = PAYLOAD_MODELS.get(kind)
    if model is None:
        if payload:
            raise validation_error({"payload": f"Kind '{kind}' does not take a payload."})
        return {}
    try:
        parsed = model.model_validate(payload)
    except ValidationError as e:
        raise validation_error({f"payload.{k}": v for k, v in pydantic_fields(e).items()}) from e
    data = parsed.model_dump(mode="json", exclude_none=True)
    if kind == "tech_stack":
        try:
            data["technologies"] = normalize_tags(data["technologies"], 20)
        except ValueError as e:
            raise validation_error({"payload.technologies": str(e)}) from e
    if kind == "alternative_resource":
        if bool(data.get("resource_id")) == bool(data.get("url")):
            raise validation_error({"payload": "Provide exactly one of resource_id or url."})
        if data.get("url"):
            try:
                data["url"] = validate_http_url(data["url"])
            except ValueError as e:
                raise validation_error({"payload.url": str(e)}) from e
    return data


# Serialization -----------------------------------------------------------------------------


def serialize(items: list[Suggestion], viewer) -> list[dict]:
    users = load_users(s.author_id for s in items)
    states = viewer_states("suggestion", items, viewer)
    out = []
    for s in items:
        ttype, tid = s.target
        state = states[s.id]
        if viewer is not None:
            target = db.session.get(model_for(ttype), tid)
            state["can_set_status"] = owner_id_of(target) == viewer.id or is_mod(viewer)
        else:
            state["can_set_status"] = False
        out.append(
            {
                "id": str(s.id),
                "target": {"type": ttype, "id": str(tid)},
                "author": user_summary(users.get(s.author_id)),
                "kind": s.kind,
                "title": s.title,
                "body": s.body,
                "payload": s.payload,
                "status": s.status,
                "owner_response": s.owner_response,
                "status_changed_at": s.status_changed_at,
                "ai_assisted": s.ai_assisted,
                "counts": {"votes": s.vote_count},
                "moderation_status": s.moderation_status,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "viewer": state,
            }
        )
    return out


def list_stmt(target_type: str, target_id, viewer, kind: str | None, status: str | None, sort: str):
    col = getattr(Suggestion, f"{target_type}_id")
    visible = and_(Suggestion.deleted_at.is_(None), Suggestion.moderation_status == "published")
    if viewer is not None:
        if is_mod(viewer):
            visible = Suggestion.deleted_at.is_(None)
        else:
            visible = or_(
                visible,
                and_(
                    Suggestion.deleted_at.is_(None),
                    Suggestion.moderation_status == "hidden",
                    Suggestion.author_id == viewer.id,
                ),
            )
    stmt = select(Suggestion).where(col == target_id, visible)
    if kind:
        if kind not in enums.SUGGESTION_KINDS[target_type]:
            raise bad_request(f"Unknown kind '{kind}'.")
        stmt = stmt.where(Suggestion.kind == kind)
    if status:
        if status not in enums.SUGGESTION_STATUSES:
            raise bad_request(f"Unknown status '{status}'.")
        stmt = stmt.where(Suggestion.status == status)
    if sort == "recent":
        return stmt.order_by(Suggestion.created_at.desc())
    if sort == "top":
        return stmt.order_by(Suggestion.vote_count.desc(), Suggestion.created_at.desc())
    raise bad_request(f"Unknown sort '{sort}'.")


# Mutations ---------------------------------------------------------------------------------


def create(target_type: str, target_id, user, body) -> Suggestion:
    model = model_for(target_type)
    target = get_or_404(model, target_id, user)
    if body.kind not in enums.SUGGESTION_KINDS[target_type]:
        raise validation_error(
            {"kind": f"Must be one of: {', '.join(enums.SUGGESTION_KINDS[target_type])}."}
        )
    payload = validate_payload(body.kind, body.payload)
    s = Suggestion(
        author_id=user.id,
        kind=body.kind,
        title=body.title,
        body=body.body,
        payload=payload,
        ai_assisted=body.ai_assisted,
        **{f"{target_type}_id": target.id},
    )
    db.session.add(s)
    db.session.flush()
    bump(model, target.id, "suggestion_count", 1, touch_activity=True)
    notify(owner_id_of(target), user, "suggestion_on_content", target_type, target, snippet_text=body.title)
    db.session.commit()
    return s


def get_suggestion(suggestion_id, viewer) -> Suggestion:
    s = db.session.get(Suggestion, suggestion_id)
    if s is None or not can_view(s, viewer):
        raise not_found()
    ttype, tid = s.target
    get_or_404(model_for(ttype), tid, viewer)
    return s


def update(suggestion_id, user, body) -> Suggestion:
    s = get_suggestion(suggestion_id, user)
    ttype, tid = s.target
    target = db.session.get(model_for(ttype), tid)
    data = body.model_dump(exclude_unset=True)
    author_fields = {"title", "body", "payload", "ai_assisted"} & data.keys()
    owner_fields = {"status", "owner_response"} & data.keys()
    is_author = s.author_id == user.id
    is_target_owner = owner_id_of(target) == user.id or is_mod(user)
    if author_fields and not is_author:
        raise forbidden("Only the author can edit the suggestion text.")
    if owner_fields and not is_target_owner:
        raise forbidden("Only the owner can change the status.")
    if "title" in data and data["title"] is not None:
        s.title = data["title"]
    if "body" in data and data["body"] is not None:
        s.body = data["body"]
    if "payload" in data:
        s.payload = validate_payload(s.kind, data["payload"])
    if data.get("ai_assisted"):
        s.ai_assisted = True
    changed = False
    if "status" in data and data["status"] is not None and data["status"] != s.status:
        s.status = data["status"]
        changed = True
    if "owner_response" in data and data["owner_response"] != s.owner_response:
        s.owner_response = data["owner_response"]
        changed = True
    if changed:
        s.status_changed_at = datetime.now(UTC)
        notify(
            s.author_id,
            user,
            "suggestion_status_changed",
            "suggestion",
            s,
            snippet_text=f"{s.title}: {s.status}",
            title_obj=target,
            title_type=ttype,
        )
    db.session.commit()
    return s


def delete(suggestion_id, user) -> None:
    s = get_suggestion(suggestion_id, user)
    if s.author_id != user.id and not is_mod(user):
        raise forbidden()
    s.deleted_at = datetime.now(UTC)
    ttype, tid = s.target
    bump(model_for(ttype), tid, "suggestion_count", -1)
    db.session.commit()
