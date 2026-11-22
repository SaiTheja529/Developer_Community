"""ApiError hierarchy and JSON error envelope (spec §5.3)."""

from __future__ import annotations

import logging
from typing import Any

from flask import Flask, g, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException

log = logging.getLogger("devcommons.errors")


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details
        self.headers = headers or {}


# Convenience constructors -------------------------------------------------------------


def bad_request(message: str = "Bad request.", details: dict | None = None) -> ApiError:
    return ApiError("bad_request", message, 400, details)


def validation_error(fields: dict[str, str], message: str = "Some fields are invalid.") -> ApiError:
    return ApiError("validation_error", message, 400, {"fields": fields})


def unauthenticated(message: str = "Authentication required.") -> ApiError:
    return ApiError("unauthenticated", message, 401)


def forbidden(message: str = "You are not allowed to do that.") -> ApiError:
    return ApiError("forbidden", message, 403)


def not_found(message: str = "Not found.") -> ApiError:
    return ApiError("not_found", message, 404)


def conflict(message: str = "Conflict.", details: dict | None = None) -> ApiError:
    return ApiError("conflict", message, 409, details)


def duplicate(existing_id: str, message: str = "This has already been submitted.") -> ApiError:
    return ApiError("duplicate", message, 409, {"existing_id": str(existing_id)})


def rate_limited(retry_after: int, message: str = "Too many requests. Slow down.") -> ApiError:
    return ApiError("rate_limited", message, 429, {"retry_after": retry_after}, {"Retry-After": str(retry_after)})


# Handlers -------------------------------------------------------------------------------

_HTTP_CODE_MAP = {
    400: ("bad_request", "Bad request."),
    401: ("unauthenticated", "Authentication required."),
    403: ("forbidden", "You are not allowed to do that."),
    404: ("not_found", "Not found."),
    405: ("bad_request", "Method not allowed."),
    409: ("conflict", "Conflict."),
    413: ("payload_too_large", "Request body is too large (max 256 KB)."),
    415: ("bad_request", "Unsupported media type. Send JSON."),
    429: ("rate_limited", "Too many requests. Slow down."),
}


def _envelope(code: str, message: str, status: int, details: dict | None = None, headers: dict | None = None):
    body: dict[str, Any] = {"code": code, "message": message, "request_id": getattr(g, "request_id", None)}
    if details:
        body["details"] = details
    resp = jsonify({"error": body})
    resp.status_code = status
    for k, v in (headers or {}).items():
        resp.headers[k] = v
    return resp


def pydantic_fields(exc: ValidationError) -> dict[str, str]:
    fields: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()) if p != "__root__") or "_"
        msg = err.get("msg", "Invalid value.")
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, ") :]
        fields.setdefault(loc, msg)
    return fields


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def _api_error(e: ApiError):
        return _envelope(e.code, e.message, e.status, e.details, e.headers)

    @app.errorhandler(ValidationError)
    def _pydantic(e: ValidationError):
        return _envelope("validation_error", "Some fields are invalid.", 400, {"fields": pydantic_fields(e)})

    @app.errorhandler(HTTPException)
    def _http(e: HTTPException):
        status = e.code or 500
        code, message = _HTTP_CODE_MAP.get(status, ("internal_error", "Something went wrong."))
        headers = {}
        if status == 429:
            retry = getattr(e, "retry_after", None)
            if e.response is not None and e.response.headers.get("Retry-After"):
                retry = e.response.headers.get("Retry-After")
            if retry:
                headers["Retry-After"] = str(retry)
        return _envelope(code, message, status, None, headers)

    @app.errorhandler(Exception)
    def _unhandled(e: Exception):
        log.exception("unhandled_error", extra={"request_id": getattr(g, "request_id", None)})
        try:
            from app.extensions import db

            db.session.rollback()
        except Exception:  # pragma: no cover
            pass
        return _envelope("internal_error", "Something went wrong.", 500)
