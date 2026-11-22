"""AI chat: conversation setup, streaming with keepalives, cancel/error handling, auto-title (spec §9.3)."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

from flask import g
from sqlalchemy import delete, func, select, update

from app.common.content import load_target
from app.common.errors import ApiError, not_found, validation_error
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.ai import context_builder
from app.modules.ai.client import AIError, StreamEvent, get_ai_client
from app.modules.ai.models import AIConversation, AIMessage
from app.modules.ai.prompt_loader import render, system_prompt
from app.modules.ai.usage import record_usage

log = logging.getLogger("devcommons.ai.chat")

WINDOW_TOKENS = 12_000
CHARS_PER_TOKEN = 4
KEEPALIVE_SECONDS = 15
_DONE = object()


@dataclass
class Prepared:
    """Plain values only: ORM objects would be detached by the time the SSE generator runs."""

    conversation_id: object
    user_message_id: object
    assistant_message_id: object
    user_message_content: str
    instructions: str
    messages: list[dict]
    context_sources: list[dict]
    first_exchange: bool
    user_id: object
    request_id: str
    feature: str = "chat"
    started: float = field(default_factory=time.monotonic)

    def meta(self) -> dict:
        return {
            "conversation_id": str(self.conversation_id),
            "user_message_id": str(self.user_message_id),
            "assistant_message_id": str(self.assistant_message_id),
            "context_sources": self.context_sources,
        }


def _ts() -> datetime:
    """Explicit, strictly increasing timestamps (now() is constant within a transaction)."""
    time.sleep(0.000002)
    return datetime.now(UTC)


# Serialization ---------------------------------------------------------------------------------


def conversation_summary(c: AIConversation, viewer) -> dict:
    ctx = None
    if c.context_type and c.context_id:
        from app.common.content import can_view, model_for

        obj = db.session.get(model_for(c.context_type), c.context_id)
        title = (getattr(obj, "name", None) or getattr(obj, "title", None)) if obj and can_view(obj, viewer) else None
        ctx = {"type": c.context_type, "id": str(c.context_id), "title": title}
    return {
        "id": str(c.id),
        "title": c.title,
        "context": ctx,
        "message_count": c.message_count,
        "last_message_at": c.last_message_at,
        "created_at": c.created_at,
    }


def message_dict(m: AIMessage) -> dict:
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "status": m.status,
        "context_sources": m.context_sources,
        "error_code": m.error_code,
        "created_at": m.created_at,
    }


def get_owned_conversation(conversation_id, user, lock: bool = False) -> AIConversation:
    stmt = select(AIConversation).where(AIConversation.id == conversation_id)
    if lock:
        stmt = stmt.with_for_update()
    c = db.session.execute(stmt).scalar_one_or_none()
    if c is None or c.user_id != user.id or c.deleted_at is not None:
        raise not_found()
    return c


# Prompt assembly -------------------------------------------------------------------------------


def _instructions(conv: AIConversation, user) -> tuple[str, list[dict]]:
    instructions, _ = system_prompt("chat")
    built = context_builder.build(conv.context_type, conv.context_id, user)
    if built.text:
        ctx_text, _ = render("chat_context", CONTEXT=built.text)
        instructions = f"{instructions}\n\n{ctx_text}"
    return instructions, built.sources


def _history_window(conv_id, exclude_ids: set, new_text: str) -> list[dict]:
    budget = WINDOW_TOKENS * CHARS_PER_TOKEN - len(new_text)
    rows = db.session.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv_id)
        .order_by(AIMessage.created_at.desc())
        .limit(200)
    ).scalars().all()
    picked: list[dict] = []
    for m in rows:
        if m.id in exclude_ids:
            continue
        if m.role == "assistant" and (m.status not in ("complete", "cancelled") or not m.content):
            continue
        if len(m.content) > budget:
            break
        budget -= len(m.content)
        picked.append({"role": m.role, "content": m.content})
    picked.reverse()
    picked.append({"role": "user", "content": new_text})
    return picked


def prepare(user, body) -> Prepared:
    s = get_settings()
    if len(body.message) > s.AI_MAX_INPUT_CHARS:
        raise validation_error({"message": f"Message must be at most {s.AI_MAX_INPUT_CHARS} characters."})
    if body.conversation_id is not None:
        conv = get_owned_conversation(body.conversation_id, user, lock=True)
    else:
        ctx_type = body.context.type if body.context else None
        ctx_id = body.context.id if body.context else None
        if ctx_type:
            load_target(ctx_type, ctx_id, user)  # 404 if the viewer cannot see it
        conv = AIConversation(user_id=user.id, context_type=ctx_type, context_id=ctx_id)
        db.session.add(conv)
        db.session.flush()
    first = conv.message_count == 0
    user_msg = AIMessage(
        conversation_id=conv.id, role="user", content=body.message, status="complete", created_at=_ts()
    )
    db.session.add(user_msg)
    db.session.flush()
    instructions, sources = _instructions(conv, user)
    asst = AIMessage(
        conversation_id=conv.id, role="assistant", content="", status="streaming", context_sources=sources,
        model=s.ai_model, created_at=_ts(),
    )
    db.session.add(asst)
    db.session.flush()
    messages = _history_window(conv.id, {user_msg.id, asst.id}, body.message)
    db.session.commit()
    return Prepared(
        conv.id, user_msg.id, asst.id, body.message, instructions, messages, sources, first, user.id,
        g.get("request_id", ""),
    )


def prepare_regenerate(user, conversation_id) -> Prepared:
    s = get_settings()
    conv = get_owned_conversation(conversation_id, user, lock=True)
    last = db.session.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv.id)
        .order_by(AIMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if last is None:
        raise ApiError("conflict", "Nothing to regenerate yet.", 409)
    if last.role == "assistant":
        db.session.execute(delete(AIMessage).where(AIMessage.id == last.id))
        db.session.execute(
            update(AIConversation)
            .where(AIConversation.id == conv.id)
            .values(message_count=func.greatest(AIConversation.message_count - 1, 0))
        )
    user_msg = db.session.execute(
        select(AIMessage)
        .where(AIMessage.conversation_id == conv.id, AIMessage.role == "user")
        .order_by(AIMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if user_msg is None:
        raise ApiError("conflict", "Nothing to regenerate yet.", 409)
    instructions, sources = _instructions(conv, user)
    asst = AIMessage(
        conversation_id=conv.id, role="assistant", content="", status="streaming", context_sources=sources,
        model=s.ai_model, created_at=_ts(),
    )
    db.session.add(asst)
    db.session.flush()
    messages = _history_window(conv.id, {user_msg.id, asst.id}, user_msg.content)
    db.session.commit()
    return Prepared(
        conv.id, user_msg.id, asst.id, user_msg.content, instructions, messages, sources, False, user.id,
        g.get("request_id", ""),
    )


# Streaming ---------------------------------------------------------------------------------------


class ChatRun:
    """Runs the model stream on a worker thread so the SSE generator can emit keepalives."""

    def __init__(self, prepared: Prepared, added_messages: int = 2):
        self.p = prepared
        self.parts: list[str] = []
        self.usage: StreamEvent | None = None
        self.model: str = get_settings().ai_model
        self.finalized = False
        self._stop = threading.Event()
        self._added_messages = added_messages

    def _worker(self, q: queue.Queue, client, s) -> None:
        try:
            for ev in client.stream_text(
                instructions=self.p.instructions,
                messages=self.p.messages,
                max_output_tokens=s.AI_MAX_OUTPUT_TOKENS_CHAT,
                request_id=self.p.request_id,
            ):
                if self._stop.is_set():
                    break
                q.put(ev)
        except AIError as e:
            q.put(StreamEvent("error", code=e.code, message=e.message))
        except Exception:  # pragma: no cover
            log.exception("ai_stream_worker_failed")
            q.put(StreamEvent("error", code="upstream_error", message="The AI service returned an error."))
        finally:
            q.put(_DONE)

    def events(self):
        """Yields (event_name, data). event_name 'keepalive' means: send an SSE comment."""
        s = get_settings()
        client = get_ai_client()
        q: queue.Queue = queue.Queue()
        threading.Thread(target=self._worker, args=(q, client, s), daemon=True).start()
        deadline = self.p.started + s.AI_STREAM_MAX_SECONDS
        error: tuple[str, str] | None = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                error = ("upstream_timeout", "The AI service took too long. Your message was saved; try regenerating.")
                break
            try:
                ev = q.get(timeout=min(KEEPALIVE_SECONDS, remaining))
            except queue.Empty:
                if not self.parts:
                    yield "keepalive", None
                continue
            if ev is _DONE:
                break
            if ev.model:
                self.model = ev.model
            if ev.kind == "delta":
                self.parts.append(ev.text)
                yield "delta", {"text": ev.text}
            elif ev.kind == "usage":
                self.usage = ev
            elif ev.kind == "error":
                msg = ev.message or "The AI service returned an error."
                if ev.code == "upstream_timeout":
                    msg = "The AI service took too long. Your message was saved; try regenerating."
                error = (ev.code or "upstream_error", msg)
                break
        self._stop.set()
        if error is not None:
            self._finalize("error", outcome="timeout" if error[0] == "upstream_timeout" else "error", error_code=error[0])
            yield "error", {"code": error[0], "message": error[1], "assistant_message_id": str(self.p.assistant_message_id)}
            return
        title = self._finalize("complete", outcome="success")
        yield "done", {
            "assistant_message_id": str(self.p.assistant_message_id),
            "status": "complete",
            "usage": {
                "input_tokens": self.usage.input_tokens if self.usage else 0,
                "output_tokens": self.usage.output_tokens if self.usage else 0,
            },
            "conversation_title": title,
        }

    def cancel(self) -> None:
        """Client disconnected or pressed Stop: keep the partial text with status 'cancelled'."""
        self._stop.set()
        if not self.finalized:
            try:
                self._finalize("cancelled", outcome="cancelled")
            except Exception:  # pragma: no cover
                db.session.rollback()
                log.exception("ai_cancel_finalize_failed")

    def _finalize(self, status: str, outcome: str, error_code: str | None = None) -> str:
        if self.finalized:
            return db.session.execute(
                select(AIConversation.title).where(AIConversation.id == self.p.conversation_id)
            ).scalar_one()
        self.finalized = True
        content = "".join(self.parts)
        u = self.usage
        latency = int((time.monotonic() - self.p.started) * 1000)
        db.session.execute(
            update(AIMessage)
            .where(AIMessage.id == self.p.assistant_message_id)
            .values(
                content=content,
                status=status,
                input_tokens=u.input_tokens if u else None,
                output_tokens=u.output_tokens if u else None,
                model=self.model,
                error_code=error_code,
            )
        )
        db.session.execute(
            update(AIConversation)
            .where(AIConversation.id == self.p.conversation_id)
            .values(
                message_count=AIConversation.message_count + self._added_messages,
                last_message_at=datetime.now(UTC),
            )
        )
        record_usage(
            user_id=self.p.user_id,
            feature=self.p.feature,
            model=self.model,
            input_tokens=u.input_tokens if u else 0,
            cached_input_tokens=u.cached_input_tokens if u else 0,
            output_tokens=u.output_tokens if u else 0,
            latency_ms=latency,
            outcome=outcome,
            error_code=error_code,
            commit=False,
        )
        db.session.commit()
        title = db.session.execute(
            select(AIConversation.title).where(AIConversation.id == self.p.conversation_id)
        ).scalar_one()
        if status == "complete" and self.p.first_exchange:
            title = self._auto_title(content)
        return title

    def _auto_title(self, reply: str) -> str:
        fallback = self.p.user_message_content.strip().replace("\n", " ")[:60] or "New conversation"
        title = fallback
        client = get_ai_client()
        started = time.monotonic()
        outcome, model, i, o, err = "success", self.model, 0, 0, None
        try:
            instructions, _ = system_prompt("chat_title")
            res = client.generate_text(
                instructions=instructions,
                input=f"User: {self.p.user_message_content[:1000]}\nAssistant: {reply[:1000]}",
                max_output_tokens=20,
                request_id=self.p.request_id,
            )
            model, i, o = res.model, res.input_tokens, res.output_tokens
            candidate = res.text.strip().strip('"').strip("'").strip()
            if candidate:
                title = candidate[:120]
        except AIError as e:
            outcome, err = "error", e.code
        except Exception:  # pragma: no cover
            outcome, err = "error", "upstream_error"
        db.session.execute(update(AIConversation).where(AIConversation.id == self.p.conversation_id).values(title=title))
        record_usage(
            user_id=self.p.user_id, feature="chat_title", model=model, input_tokens=i, output_tokens=o,
            latency_ms=int((time.monotonic() - started) * 1000), outcome=outcome, error_code=err, commit=False,
        )
        db.session.commit()
        return title
