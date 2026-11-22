"""Success envelopes (spec §5.2)."""

from __future__ import annotations

import math
from typing import Any

from flask import Response, jsonify


def ok(data: Any, status: int = 200, headers: dict | None = None) -> tuple[Response, int]:
    resp = jsonify({"data": data})
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp, status


def created(data: Any) -> tuple[Response, int]:
    return ok(data, 201)


def accepted(data: Any | None = None) -> tuple[Response, int]:
    return ok(data if data is not None else {"accepted": True}, 202)


def no_content() -> tuple[str, int]:
    return "", 204


def paginated(items: list[Any], page: int, page_size: int, total: int) -> tuple[Response, int]:
    total_pages = max(1, math.ceil(total / page_size)) if page_size else 1
    return (
        jsonify(
            {
                "data": items,
                "meta": {"page": page, "page_size": page_size, "total": total, "total_pages": total_pages},
            }
        ),
        200,
    )
