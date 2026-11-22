"""/api/ai/* endpoints: SSE chat, conversations, generation, drafts, usage, status (spec §9)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

from flask import Blueprint, Response, g, stream_with_context
from pydantic import Field
from sqlalchemy import Date, cast, func, select

from app.auth.decorators import authenticate, require_auth, require_verified
from app.common.pagination import PageParams, paginate
from app.common.ratelimit import enforce
from app.common.responses import created, no_content, ok, paginated
from app.common.validation import QueryModel, parse_body, validate_query
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.ai import chat_service, generation_service
from app.modules.ai.models import AIConversation, AIDraft, AIMessage, AIUsage
from app.modules.ai.quota import ai_status_reason, ensure_ai_allowed, user_today
from app.modules.ai.schemas import (
    ChatRequest,
    ConversationPatch,
    DraftPatch,
    DraftsQuery,
    FeedbackBody,
    GenerateHarnessBody,
    GenerateIdeaBody,
    GenerateResourcesBody,
    RefineBody,
    RefineSectionBody,
    RegenerateDraftBody,
    RestoreBody,
)

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _json_default(o):
    if isinstance(o, datetime):
        return o.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(o)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=_json_default, separators=(',', ':'))}\n\n"


def _guard(generation: bool) -> None:
    ensure_ai_allowed(g.current_user, generation=generation)
    if generation:
        enforce("5 per minute", "ai_generation")
    else:
        enforce("10 per minute", "ai_chat")


def _stream(prepared, added_messages: int = 2) -> Response:
    run = chat_service.ChatRun(prepared, added_messages=added_messages)

    def gen():
        yield sse("meta", prepared.meta())
        try:
            for name, data in run.events():
                if name == "keepalive":
                    yield ": keepalive\n\n"
                else:
                    yield sse(name, data)
        except GeneratorExit:  # client disconnected / pressed Stop
            run.cancel()
            raise

    return Response(
        stream_with_context(gen()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# Chat ------------------------------------------------------------------------------------------


@bp.post("/chat")
@require_auth
@require_verified
def chat():
    _guard(generation=False)
    body = parse_body(ChatRequest)
    prepared = chat_service.prepare(g.current_user, body)
    return _stream(prepared)


@bp.post("/conversations/<uuid:conversation_id>/regenerate")
@require_auth
@require_verified
def regenerate(conversation_id: uuid.UUID):
    _guard(generation=False)
    prepared = chat_service.prepare_regenerate(g.current_user, conversation_id)
    return _stream(prepared, added_messages=1)


@bp.get("/conversations")
@require_auth
@validate_query(PageParams)
def list_conversations(query: PageParams):
    stmt = (
        select(AIConversation)
        .where(AIConversation.user_id == g.current_user.id, AIConversation.deleted_at.is_(None))
        .order_by(AIConversation.last_message_at.desc().nulls_last(), AIConversation.created_at.desc())
    )
    page = paginate(stmt, query.page, query.page_size)
    items = [chat_service.conversation_summary(c, g.current_user) for c in page.items]
    return paginated(items, page.page, page.page_size, page.total)


@bp.get("/conversations/<uuid:conversation_id>")
@require_auth
def get_conversation(conversation_id: uuid.UUID):
    conv = chat_service.get_owned_conversation(conversation_id, g.current_user)
    msgs = db.session.execute(
        select(AIMessage).where(AIMessage.conversation_id == conv.id).order_by(AIMessage.created_at)
    ).scalars().all()
    data = chat_service.conversation_summary(conv, g.current_user)
    data["messages"] = [chat_service.message_dict(m) for m in msgs]
    return ok(data)


@bp.patch("/conversations/<uuid:conversation_id>")
@require_auth
def patch_conversation(conversation_id: uuid.UUID):
    body = parse_body(ConversationPatch)
    conv = chat_service.get_owned_conversation(conversation_id, g.current_user, lock=True)
    conv.title = body.title
    db.session.commit()
    return ok(chat_service.conversation_summary(conv, g.current_user))


@bp.delete("/conversations/<uuid:conversation_id>")
@require_auth
def delete_conversation(conversation_id: uuid.UUID):
    conv = chat_service.get_owned_conversation(conversation_id, g.current_user, lock=True)
    conv.deleted_at = datetime.now(UTC)
    db.session.commit()
    return no_content()


# Generation ------------------------------------------------------------------------------------


@bp.post("/generate/harness")
@require_auth
@require_verified
def generate_harness():
    _guard(generation=True)
    body = parse_body(GenerateHarnessBody)
    draft = generation_service.generate("harness_doc", body.model_dump(mode="json"), g.current_user)
    return created(generation_service.draft_dict(draft))


@bp.post("/generate/project-idea")
@require_auth
@require_verified
def generate_project_idea():
    _guard(generation=True)
    body = parse_body(GenerateIdeaBody)
    draft = generation_service.generate("project_idea", body.model_dump(mode="json"), g.current_user)
    return created(generation_service.draft_dict(draft))


@bp.post("/generate/resources")
@require_auth
@require_verified
def generate_resources():
    _guard(generation=True)
    body = parse_body(GenerateResourcesBody)
    draft = generation_service.generate("resource_recommendations", body.model_dump(mode="json"), g.current_user)
    return created(generation_service.draft_dict(draft))


@bp.post("/refine")
@require_auth
@require_verified
def refine():
    _guard(generation=True)
    body = parse_body(RefineBody)
    return ok(generation_service.refine(body))


@bp.post("/feedback-suggestions")
@require_auth
@require_verified
def feedback_suggestions():
    _guard(generation=True)
    body = parse_body(FeedbackBody)
    draft = generation_service.generate("feedback_suggestions", body.model_dump(mode="json"), g.current_user)
    return created(generation_service.draft_dict(draft))


# Drafts ----------------------------------------------------------------------------------------


@bp.get("/drafts")
@require_auth
@validate_query(DraftsQuery)
def list_drafts(query: DraftsQuery):
    stmt = select(AIDraft).where(AIDraft.user_id == g.current_user.id)
    if query.task:
        stmt = stmt.where(AIDraft.task == query.task)
    if query.status:
        stmt = stmt.where(AIDraft.status == query.status)
    page = paginate(stmt.order_by(AIDraft.updated_at.desc()), query.page, query.page_size)
    return paginated([generation_service.draft_dict(d) for d in page.items], page.page, page.page_size, page.total)


@bp.get("/drafts/<uuid:draft_id>")
@require_auth
def get_draft(draft_id: uuid.UUID):
    d = generation_service.get_owned_draft(draft_id, g.current_user)
    data = generation_service.draft_dict(d)
    data["history"] = generation_service.draft_history(d)
    return ok(data)


@bp.patch("/drafts/<uuid:draft_id>")
@require_auth
def patch_draft(draft_id: uuid.UUID):
    body = parse_body(DraftPatch)
    d = generation_service.get_owned_draft(draft_id, g.current_user, lock=True)
    return ok(generation_service.draft_dict(generation_service.patch_output(d, body.output)))


@bp.post("/drafts/<uuid:draft_id>/refine-section")
@require_auth
@require_verified
def refine_section(draft_id: uuid.UUID):
    d = generation_service.get_owned_draft(draft_id, g.current_user)
    _guard(generation=True)
    body = parse_body(RefineSectionBody)
    d = generation_service.refine_section(d, body.field, body.instruction)
    return ok(generation_service.draft_dict(d))


@bp.post("/drafts/<uuid:draft_id>/regenerate")
@require_auth
@require_verified
def regenerate_draft(draft_id: uuid.UUID):
    d = generation_service.get_owned_draft(draft_id, g.current_user)
    _guard(generation=True)
    body = parse_body(RegenerateDraftBody, allow_empty=True)
    d = generation_service.regenerate(d, g.current_user, body.additional_context)
    return ok(generation_service.draft_dict(d))


@bp.post("/drafts/<uuid:draft_id>/restore")
@require_auth
def restore_draft(draft_id: uuid.UUID):
    body = parse_body(RestoreBody)
    d = generation_service.get_owned_draft(draft_id, g.current_user, lock=True)
    return ok(generation_service.draft_dict(generation_service.restore(d, body.history_index)))


@bp.post("/drafts/<uuid:draft_id>/discard")
@require_auth
def discard_draft(draft_id: uuid.UUID):
    d = generation_service.get_owned_draft(draft_id, g.current_user, lock=True)
    return ok(generation_service.draft_dict(generation_service.discard(d)))


# Usage & status --------------------------------------------------------------------------------


class UsageQuery(QueryModel):
    days: int = Field(30, ge=1, le=90)


@bp.get("/usage")
@require_auth
@validate_query(UsageQuery)
def usage(query: UsageQuery):
    since = datetime.now(UTC) - timedelta(days=query.days)
    day = cast(AIUsage.created_at, Date)
    rows = db.session.execute(
        select(
            day,
            func.coalesce(func.sum(AIUsage.input_tokens + AIUsage.output_tokens), 0),
            func.count(),
            func.coalesce(func.sum(AIUsage.estimated_cost_usd), 0),
        )
        .where(AIUsage.user_id == g.current_user.id, AIUsage.created_at >= since)
        .group_by(day)
        .order_by(day)
    ).all()
    is_admin = g.current_user.role == "admin"
    daily = []
    for d, tokens, requests, cost in rows:
        item = {"date": d.isoformat(), "tokens": int(tokens), "requests": requests}
        if is_admin:
            item["cost_usd"] = round(float(cost), 6)
        daily.append(item)
    return ok({"today": user_today(g.current_user), "daily": daily})


@bp.get("/status")
def status():
    s = get_settings()
    authenticate(strict=False)
    reason = ai_status_reason()
    data = {"enabled": reason is None, "model_label": s.AI_MODEL_LABEL}
    if reason:
        data["reason"] = reason
    if g.current_user is not None:
        data["today"] = user_today(g.current_user)
    return ok(data)
