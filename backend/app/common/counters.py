"""Atomic counter helpers and counter rebuild (spec §5.10)."""

from __future__ import annotations

from sqlalchemy import func, text, update

from app.extensions import db


def bump(model, row_id, field: str, delta: int = 1, touch_activity: bool = False) -> None:
    """UPDATE ... SET field = field + delta (never read-modify-write). Clamped at 0."""
    col = getattr(model, field)
    values = {field: func.greatest(col + delta, 0)}
    if touch_activity and hasattr(model, "last_activity_at"):
        values["last_activity_at"] = func.now()
    db.session.execute(update(model).where(model.id == row_id).values(**values))


def touch_activity(model, row_id) -> None:
    if hasattr(model, "last_activity_at"):
        db.session.execute(update(model).where(model.id == row_id).values(last_activity_at=func.now()))


_REBUILD_SQL = [
    # Harnesses
    """
    UPDATE harnesses h SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='harness' AND v.target_id=h.id AND v.kind='upvote'),
      comment_count = (SELECT count(*) FROM comments c WHERE c.harness_id=h.id AND c.deleted_at IS NULL),
      suggestion_count = (SELECT count(*) FROM suggestions s WHERE s.harness_id=h.id AND s.deleted_at IS NULL),
      review_count = (SELECT count(*) FROM harness_reviews r WHERE r.harness_id=h.id AND r.deleted_at IS NULL),
      bookmark_count = (SELECT count(*) FROM bookmarks b WHERE b.target_type='harness' AND b.target_id=h.id)
    """,
    # Ideas
    """
    UPDATE ideas i SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='idea' AND v.target_id=i.id AND v.kind='upvote'),
      interest_count = (SELECT count(*) FROM votes v WHERE v.target_type='idea' AND v.target_id=i.id AND v.kind='interest'),
      comment_count = (SELECT count(*) FROM comments c WHERE c.idea_id=i.id AND c.deleted_at IS NULL),
      suggestion_count = (SELECT count(*) FROM suggestions s WHERE s.idea_id=i.id AND s.deleted_at IS NULL),
      collaborator_count = (SELECT count(*) FROM collaboration_requests cr WHERE cr.idea_id=i.id AND cr.status='accepted'),
      bookmark_count = (SELECT count(*) FROM bookmarks b WHERE b.target_type='idea' AND b.target_id=i.id)
    """,
    # Resources
    """
    UPDATE resources r SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='resource' AND v.target_id=r.id AND v.kind='upvote'),
      comment_count = (SELECT count(*) FROM comments c WHERE c.resource_id=r.id AND c.deleted_at IS NULL),
      suggestion_count = (SELECT count(*) FROM suggestions s WHERE s.resource_id=r.id AND s.deleted_at IS NULL),
      bookmark_count = (SELECT count(*) FROM bookmarks b WHERE b.target_type='resource' AND b.target_id=r.id),
      collection_count = (SELECT count(*) FROM collection_items ci WHERE ci.resource_id=r.id),
      broken_report_count = (SELECT count(*) FROM reports rp WHERE rp.target_type='resource' AND rp.target_id=r.id
                             AND rp.status='open' AND rp.reason IN ('broken_link','outdated'))
    """,
    # Collections
    """
    UPDATE collections c SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='collection' AND v.target_id=c.id AND v.kind='upvote'),
      comment_count = (SELECT count(*) FROM comments cm WHERE cm.collection_id=c.id AND cm.deleted_at IS NULL),
      bookmark_count = (SELECT count(*) FROM bookmarks b WHERE b.target_type='collection' AND b.target_id=c.id),
      item_count = (SELECT count(*) FROM collection_items ci WHERE ci.collection_id=c.id)
    """,
    # Comments
    """
    UPDATE comments c SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='comment' AND v.target_id=c.id AND v.kind='upvote'),
      reply_count = (SELECT count(*) FROM comments r WHERE r.parent_id=c.id AND r.deleted_at IS NULL)
    """,
    """
    UPDATE suggestions s SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='suggestion' AND v.target_id=s.id AND v.kind='upvote')
    """,
    """
    UPDATE harness_reviews r SET
      vote_count = (SELECT count(*) FROM votes v WHERE v.target_type='review' AND v.target_id=r.id AND v.kind='upvote')
    """,
    """
    UPDATE ai_conversations c SET
      message_count = (SELECT count(*) FROM ai_messages m WHERE m.conversation_id=c.id)
    """,
]


def rebuild_all() -> None:
    for sql in _REBUILD_SQL:
        db.session.execute(text(sql))
    db.session.commit()
