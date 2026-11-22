"""OpenAI wrapper (spec §9.2). This is the ONLY module that imports `openai`.

Everything else depends on the `AIClient` protocol, so tests use `FakeAIClient`.
"""

from __future__ import annotations

import logging
import time
import types
import typing
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel

log = logging.getLogger("devcommons.ai")


@dataclass
class StreamEvent:
    kind: str  # delta | usage | error
    text: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    model: str | None = None
    code: str | None = None
    message: str | None = None


@dataclass
class StructuredResult:
    parsed: BaseModel | None
    refusal: str | None
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    model: str


@dataclass
class TextResult:
    text: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    model: str


class AIError(Exception):
    """code: upstream_timeout | upstream_error | ai_unavailable | invalid_output"""

    def __init__(self, code: str, message: str = "", model: str | None = None):
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.model = model


class AIClient(Protocol):
    def stream_text(
        self, *, instructions: str, messages: list[dict], max_output_tokens: int, request_id: str
    ) -> Iterator[StreamEvent]: ...

    def generate_structured(
        self, *, instructions: str, input: str, schema: type[BaseModel], max_output_tokens: int, request_id: str
    ) -> StructuredResult: ...

    def generate_text(self, *, instructions: str, input: str, max_output_tokens: int, request_id: str) -> TextResult: ...


# OpenAI implementation ------------------------------------------------------------------------


class OpenAIClient:
    def __init__(self, settings):
        from openai import OpenAI

        self._client = OpenAI(
            api_key=settings.OPENAI_API_KEY, timeout=settings.OPENAI_TIMEOUT_SECONDS, max_retries=2
        )
        self._model = settings.OPENAI_MODEL
        self._fallback = settings.OPENAI_FALLBACK_MODEL

    # Error mapping / fallback -----------------------------------------------------------------

    @staticmethod
    def _is_model_unavailable(exc: Exception) -> bool:
        import openai

        if isinstance(exc, openai.NotFoundError):
            return True
        if isinstance(exc, openai.APIStatusError) and exc.status_code in (503, 529):
            return True
        msg = str(exc).lower()
        return "model" in msg and ("not found" in msg or "does not exist" in msg or "overloaded" in msg)

    def _map_error(self, exc: Exception, model: str) -> AIError:
        import openai

        if isinstance(exc, openai.APITimeoutError):
            return AIError("upstream_timeout", "The AI service took too long.", model)
        if isinstance(exc, openai.RateLimitError):
            return AIError("ai_unavailable", "The AI service is busy. Try again shortly.", model)
        if self._is_model_unavailable(exc):
            return AIError("ai_unavailable", "The AI model is unavailable right now.", model)
        if isinstance(exc, openai.APIConnectionError):
            return AIError("upstream_error", "Couldn't reach the AI service.", model)
        return AIError("upstream_error", "The AI service returned an error.", model)

    def _with_fallback(self, fn):
        try:
            return fn(self._model)
        except AIError:
            raise
        except Exception as exc:
            if self._fallback and self._is_model_unavailable(exc):
                log.error("ai_model_unavailable_using_fallback", extra={"model": self._model})
                try:
                    return fn(self._fallback)
                except Exception as exc2:
                    raise self._map_error(exc2, self._fallback) from exc2
            if self._is_model_unavailable(exc):
                log.error("ai_model_unavailable", extra={"model": self._model})
            raise self._map_error(exc, self._model) from exc

    @staticmethod
    def _usage(u) -> tuple[int, int, int]:
        if u is None:
            return 0, 0, 0
        details = getattr(u, "input_tokens_details", None)
        cached = getattr(details, "cached_tokens", 0) if details is not None else 0
        return u.input_tokens or 0, u.output_tokens or 0, cached or 0

    # API ----------------------------------------------------------------------------------

    def stream_text(self, *, instructions, messages, max_output_tokens, request_id):
        def open_stream(model):
            return model, self._client.responses.create(
                model=model,
                instructions=instructions,
                input=messages,
                max_output_tokens=max_output_tokens,
                stream=True,
                store=False,  # we keep history ourselves; don't persist at OpenAI
                metadata={"request_id": request_id},
            )

        model, stream = self._with_fallback(open_stream)
        try:
            for event in stream:
                etype = getattr(event, "type", "")
                if etype in ("response.output_text.delta", "response.refusal.delta"):
                    yield StreamEvent("delta", text=event.delta, model=model)
                elif etype in ("response.completed", "response.incomplete"):
                    i, o, c = self._usage(getattr(event.response, "usage", None))
                    yield StreamEvent("usage", input_tokens=i, output_tokens=o, cached_input_tokens=c, model=model)
                elif etype in ("response.failed", "error"):
                    yield StreamEvent("error", code="upstream_error", message="The AI service returned an error.", model=model)
                    return
        except Exception as exc:  # network errors mid-stream
            err = self._map_error(exc, model)
            yield StreamEvent("error", code=err.code, message=err.message, model=model)
        finally:
            close = getattr(stream, "close", None)
            if close:
                try:
                    close()
                except Exception:  # pragma: no cover
                    pass

    def generate_structured(self, *, instructions, input, schema, max_output_tokens, request_id):
        def call(model):
            resp = self._client.responses.parse(
                model=model,
                instructions=instructions,
                input=input,
                text_format=schema,
                max_output_tokens=max_output_tokens,
                store=False,
                metadata={"request_id": request_id},
            )
            refusal = None
            for item in getattr(resp, "output", []) or []:
                for content in getattr(item, "content", []) or []:
                    if getattr(content, "type", None) == "refusal":
                        refusal = getattr(content, "refusal", None)
            i, o, c = self._usage(resp.usage)
            return StructuredResult(
                parsed=resp.output_parsed, refusal=refusal, input_tokens=i, output_tokens=o, cached_input_tokens=c,
                model=getattr(resp, "model", model),
            )

        try:
            return self._with_fallback(call)
        except AIError:
            raise
        except Exception as exc:  # pragma: no cover - parse failures
            raise AIError("invalid_output", str(exc), self._model) from exc

    def generate_text(self, *, instructions, input, max_output_tokens, request_id):
        def call(model):
            resp = self._client.responses.create(
                model=model,
                instructions=instructions,
                input=input,
                max_output_tokens=max_output_tokens,
                store=False,
                metadata={"request_id": request_id},
            )
            i, o, c = self._usage(resp.usage)
            return TextResult(text=resp.output_text or "", input_tokens=i, output_tokens=o, cached_input_tokens=c,
                              model=getattr(resp, "model", model))

        return self._with_fallback(call)


# Fake implementation (tests and keyless local development) ----------------------------------


def fake_instance(schema: type[BaseModel], hint: str = "") -> BaseModel:
    """Build a valid instance of `schema` with plausible placeholder values."""

    def value_for(annotation, name: str):
        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)
        if origin is typing.Literal:
            return args[0]
        if origin in (typing.Union, types.UnionType):
            non_none = [a for a in args if a is not type(None)]
            optional = len(non_none) < len(args)
            if optional and name in ("evidence_path", "hub_resource_id", "url"):
                return None
            return value_for(non_none[0], name)
        if origin is list:
            inner = args[0] if args else str
            return [value_for(inner, name) for _ in range(2)]
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return fake_instance(annotation, hint).model_dump()
        if annotation is int:
            return 1
        if annotation is float:
            return 0.5
        if annotation is bool:
            return False
        return f"Sample {name.replace('_', ' ')}{(' for ' + hint) if hint else ''}"

    data = {name: value_for(field.annotation, name) for name, field in schema.model_fields.items()}
    return schema.model_validate(data)


class FakeAIClient:
    """Deterministic client. Configure per test via attributes:

    - stream_chunks: list[str] to stream for chat (default echoes the user message)
    - structured: dict[schema_name -> dict | list[dict] | Exception] overrides
    - fail_stream: AIError to raise / emit during streaming
    - delay_seconds: sleep between chunks
    """

    def __init__(self, model: str = "fake-model"):
        self.model = model
        self.stream_chunks: list[str] | None = None
        self.structured: dict[str, Any] = {}
        self.fail_stream: AIError | None = None
        self.delay_seconds: float = 0.0
        self.calls: list[dict] = []

    def stream_text(self, *, instructions, messages, max_output_tokens, request_id):
        self.calls.append({"kind": "stream", "instructions": instructions, "messages": messages})
        if self.fail_stream is not None and self.fail_stream.code == "ai_unavailable":
            raise self.fail_stream
        last = messages[-1]["content"] if messages else ""
        chunks = self.stream_chunks or ["Here is a sample answer ", "about: ", last[:80]]
        for chunk in chunks:
            if self.delay_seconds:
                time.sleep(self.delay_seconds)
            yield StreamEvent("delta", text=chunk, model=self.model)
        if self.fail_stream is not None:
            yield StreamEvent("error", code=self.fail_stream.code, message=self.fail_stream.message, model=self.model)
            return
        yield StreamEvent("usage", input_tokens=100, output_tokens=20, cached_input_tokens=0, model=self.model)

    def generate_structured(self, *, instructions, input, schema, max_output_tokens, request_id):
        self.calls.append({"kind": "structured", "schema": schema.__name__, "instructions": instructions, "input": input})
        override = self.structured.get(schema.__name__)
        if isinstance(override, list):
            override = override.pop(0) if override else None
        if isinstance(override, Exception):
            raise override
        if isinstance(override, dict) and override.get("__refusal__"):
            return StructuredResult(None, override["__refusal__"], 50, 5, 0, self.model)
        parsed = schema.model_validate(override) if isinstance(override, dict) else fake_instance(schema)
        return StructuredResult(parsed, None, 200, 150, 0, self.model)

    def generate_text(self, *, instructions, input, max_output_tokens, request_id):
        self.calls.append({"kind": "text", "instructions": instructions, "input": input})
        return TextResult(text="Sample conversation title", input_tokens=20, output_tokens=5,
                          cached_input_tokens=0, model=self.model)


def get_ai_client() -> AIClient:
    from flask import current_app

    client = current_app.extensions.get("ai_client")
    if client is None:
        s = current_app.extensions["settings"]
        client = FakeAIClient() if s.AI_PROVIDER == "fake" else OpenAIClient(s)
        current_app.extensions["ai_client"] = client
    return client
