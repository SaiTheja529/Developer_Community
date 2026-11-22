"""Request IDs, timing, JSON access logs and security headers (spec §5.9, §12)."""

from __future__ import annotations

import logging
import re
import sys
import time

from flask import Flask, g, request
from pythonjsonlogger.json import JsonFormatter
from ulid import ULID

access_log = logging.getLogger("devcommons.access")
_REQ_ID_RE = re.compile(r"^[A-Za-z0-9_\-.:]{1,100}$")


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        handler.setFormatter(
            JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s", rename_fields={"levelname": "level"})
        )
    else:
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root.addHandler(handler)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("werkzeug").setLevel(logging.WARNING)


def new_request_id() -> str:
    return f"req_{ULID()}"


def register_request_hooks(app: Flask) -> None:
    @app.before_request
    def _start():
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if incoming and _REQ_ID_RE.match(incoming) else new_request_id()
        g.request_start = time.perf_counter()
        g.current_user = None
        g.session_id = None

    @app.after_request
    def _finish(response):
        response.headers["X-Request-ID"] = getattr(g, "request_id", "")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if app.extensions["settings"].is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
        start = getattr(g, "request_start", None)
        duration_ms = round((time.perf_counter() - start) * 1000, 1) if start else None
        user = getattr(g, "current_user", None)
        access_log.info(
            "request",
            extra={
                "request_id": getattr(g, "request_id", None),
                "method": request.method,
                "path": request.url_rule.rule if request.url_rule else "<unmatched>",
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": str(user.id) if user is not None else None,
            },
        )
        return response
