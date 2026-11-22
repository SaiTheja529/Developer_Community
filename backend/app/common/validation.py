"""Pydantic request validation helpers (spec §5, §12).

- Request bodies are validated with `extra="forbid"` (unknown fields rejected).
- Query params ignore unknown keys.
"""

from __future__ import annotations

import functools
from typing import Annotated, Any

from flask import request
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
)

from app.common.errors import ApiError, bad_request, pydantic_fields
from app.common.text import clean_optional, clean_text, normalize_tags, validate_http_url


class StrictModel(BaseModel):
    """Base for request bodies: unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


# Reusable annotated field types ---------------------------------------------------------


def Text(min_len: int = 0, max_len: int = 20000):  # noqa: N802 - type factory
    return Annotated[str, BeforeValidator(clean_text), StringConstraints(min_length=min_len, max_length=max_len)]


def OptText(max_len: int = 20000):  # noqa: N802
    # The length constraint must apply to the str branch only; on `str | None` pydantic calls
    # len(None) and raises a TypeError (HTTP 500) whenever a client sends an explicit null.
    return Annotated[
        Annotated[str, StringConstraints(max_length=max_len)] | None, BeforeValidator(clean_optional)
    ]


def _validate_url(v):
    if v is None:
        return v
    return validate_http_url(v)


def _validate_opt_url(v):
    v = clean_optional(v)
    if v is None:
        return None
    return validate_http_url(v)


Url = Annotated[str, BeforeValidator(_validate_url)]
OptUrl = Annotated[str | None, BeforeValidator(_validate_opt_url)]


def Tags(max_items: int = 8):  # noqa: N802
    return Annotated[list[str], AfterValidator(lambda v: normalize_tags(v, max_items))]


def _split_csv(v):
    if v is None or v == "":
        return []
    if isinstance(v, str):
        return [p.strip() for p in v.split(",") if p.strip()]
    return v


CsvList = Annotated[list[str], BeforeValidator(_split_csv)]

_TRUE = {"1", "true", "yes", "on"}


def _parse_bool(v):
    if isinstance(v, str):
        return v.strip().lower() in _TRUE
    return bool(v)


QueryBool = Annotated[bool, BeforeValidator(_parse_bool)]

__all__ = [
    "StrictModel",
    "QueryModel",
    "Text",
    "OptText",
    "Url",
    "OptUrl",
    "Tags",
    "CsvList",
    "QueryBool",
    "Field",
    "validate_body",
    "validate_query",
    "parse_body",
    "parse_query",
]


def parse_body(model: type[BaseModel], allow_empty: bool = False) -> Any:
    data = request.get_json(silent=True)
    if data is None:
        if allow_empty and not request.get_data():
            data = {}
        else:
            raise bad_request("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise bad_request("Request body must be a JSON object.")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise ApiError("validation_error", "Some fields are invalid.", 400, {"fields": pydantic_fields(e)}) from e


def parse_query(model: type[BaseModel]) -> Any:
    data: dict[str, Any] = {}
    for key in request.args:
        values = request.args.getlist(key)
        data[key] = values[0] if len(values) == 1 else ",".join(values)
    try:
        return model.model_validate(data)
    except ValidationError as e:
        raise bad_request("Invalid query parameters.", {"fields": pydantic_fields(e)}) from e


def validate_body(model: type[BaseModel], allow_empty: bool = False):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            kwargs["body"] = parse_body(model, allow_empty=allow_empty)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def validate_query(model: type[BaseModel]):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            kwargs["query"] = parse_query(model)
            return fn(*args, **kwargs)

        return wrapper

    return deco
