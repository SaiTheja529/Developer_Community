"""POST /api/reports (spec §8.10)."""

from __future__ import annotations

import uuid
from typing import Literal

from flask import Blueprint, g

from app.auth.decorators import require_auth, require_verified
from app.common import enums
from app.common.ratelimit import limit
from app.common.responses import created
from app.common.validation import OptText, StrictModel, parse_body
from app.modules.reports import service

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


class ReportCreate(StrictModel):
    target_type: Literal[tuple(enums.REPORT_TARGETS)]  # type: ignore[valid-type]
    target_id: uuid.UUID
    reason: Literal[tuple(enums.REPORT_REASONS)]  # type: ignore[valid-type]
    details: OptText(1000) = None


@bp.post("")
@require_auth
@require_verified
@limit("20 per day", "create_report")
def create_report():
    body = parse_body(ReportCreate)
    report = service.create_report(g.current_user, body)
    return created(service.serialize_reports([report], include_preview=False)[0])
