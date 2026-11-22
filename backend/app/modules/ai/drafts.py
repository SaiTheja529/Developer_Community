"""Linking AI drafts to published content via `source_draft_id` (spec §9.7)."""

from __future__ import annotations

from app.common.errors import validation_error
from app.extensions import db
from app.modules.ai.models import AIDraft


def claim_draft(draft_id, user, tasks: tuple[str, ...]) -> AIDraft | None:
    """Verify the draft belongs to the user and has a compatible task. Returns None when no id given."""
    if draft_id is None:
        return None
    draft = db.session.get(AIDraft, draft_id)
    if draft is None or draft.user_id != user.id or draft.task not in tasks or draft.status == "discarded":
        raise validation_error({"source_draft_id": "Unknown draft, or it cannot be used for this form."})
    return draft


def mark_published(draft: AIDraft | None, target_type: str, target_id) -> None:
    if draft is None:
        return
    draft.status = "published"
    draft.published_target_type = target_type
    draft.published_target_id = target_id
