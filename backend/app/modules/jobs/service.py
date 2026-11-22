"""Scheduled jobs (spec §8.14). Each job runs under a Postgres advisory lock."""

from __future__ import annotations

import contextlib
import logging
import zlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select, text

from app.extensions import db

log = logging.getLogger("devcommons.jobs")


@contextlib.contextmanager
def advisory_lock(name: str):
    """Yields True if the lock was acquired; overlapping runs get False and should skip."""
    key = zlib.crc32(f"devcommons:{name}".encode())
    conn = db.engine.connect()
    try:
        got = conn.execute(select(func.pg_try_advisory_lock(key))).scalar_one()
        conn.commit()
        try:
            yield bool(got)
        finally:
            if got:
                conn.execute(select(func.pg_advisory_unlock(key)))
                conn.commit()
    finally:
        conn.close()


# Link check ------------------------------------------------------------------------------------


def link_check(limit: int = 50) -> dict:
    from app.modules.resources.models import Resource
    from app.modules.resources.service import run_link_check

    live = and_(Resource.deleted_at.is_(None), Resource.status != "removed")
    stale_cutoff = datetime.now(UTC) - timedelta(days=7)
    picked: list = []

    def take(stmt):
        remaining = limit - len(picked)
        if remaining <= 0:
            return
        exclude = [r.id for r in picked]
        if exclude:
            stmt = stmt.where(Resource.id.notin_(exclude))
        picked.extend(db.session.execute(stmt.limit(remaining)).scalars().all())

    take(select(Resource).where(live, Resource.link_status == "pending").order_by(Resource.created_at))
    take(
        select(Resource)
        .where(live, or_(Resource.link_last_checked_at.is_(None), Resource.link_last_checked_at < stale_cutoff))
        .order_by(Resource.link_last_checked_at.asc().nulls_first())
    )
    take(
        select(Resource)
        .where(live, Resource.broken_report_count > 0)
        .order_by(Resource.link_last_checked_at.asc().nulls_first())
    )
    broken = 0
    for r in picked:
        try:
            if run_link_check(r):
                broken += 1
            db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception("link_check_failed", extra={"resource_id": str(r.id)})
    return {"checked": len(picked), "newly_broken": broken}


# Repo refresh ----------------------------------------------------------------------------------


def refresh_repos(limit: int = 200) -> dict:
    from app.integrations.github import GitHubError, get_client
    from app.modules.harnesses.models import Harness

    rows = db.session.execute(
        select(Harness)
        .where(Harness.deleted_at.is_(None))
        .order_by(Harness.repo_metadata_fetched_at.asc().nulls_first())
        .limit(limit)
    ).scalars().all()
    client = get_client()
    refreshed, flagged = 0, 0
    for h in rows:
        try:
            meta, _ = client.get_repo_metadata(h.repo_owner, h.repo_name)
            h.repo_metadata = meta
            refreshed += 1
            if meta.get("archived"):
                flagged += 1
        except GitHubError as e:
            if e.status == "rate_limited":
                break
            if e.status in ("not_found", "private"):
                h.repo_metadata = {**(h.repo_metadata or {}), "unavailable": True}
                flagged += 1
        h.repo_metadata_fetched_at = datetime.now(UTC)
        db.session.commit()
    return {"refreshed": refreshed, "flagged": flagged}


# Cleanup ---------------------------------------------------------------------------------------

_NO_OPEN_REPORT = (
    "NOT EXISTS (SELECT 1 FROM reports rp WHERE rp.target_type = :tt AND rp.target_id = {alias}.id "
    "AND rp.status = 'open')"
)


def _exec(sql: str, **params) -> int:
    return db.session.execute(text(sql), params).rowcount or 0


def _purge_children(target_col: str, ids_sql: str, params: dict) -> None:
    """Delete comments/suggestions/reviews/collab requests (and their votes) of the given targets."""
    if target_col == "harness_id":
        _exec(
            f"DELETE FROM votes WHERE target_type='review' AND target_id IN "
            f"(SELECT id FROM harness_reviews WHERE harness_id IN ({ids_sql}))",
            **params,
        )
        _exec(f"DELETE FROM harness_reviews WHERE harness_id IN ({ids_sql})", **params)
    if target_col in ("harness_id", "idea_id"):
        _exec(f"DELETE FROM collaboration_requests WHERE {target_col} IN ({ids_sql})", **params)
    if target_col in ("harness_id", "idea_id", "resource_id"):
        _exec(
            f"DELETE FROM votes WHERE target_type='suggestion' AND target_id IN "
            f"(SELECT id FROM suggestions WHERE {target_col} IN ({ids_sql}))",
            **params,
        )
        _exec(f"DELETE FROM suggestions WHERE {target_col} IN ({ids_sql})", **params)
    _exec(
        f"DELETE FROM votes WHERE target_type='comment' AND target_id IN "
        f"(SELECT id FROM comments WHERE {target_col} IN ({ids_sql}))",
        **params,
    )
    _exec(f"DELETE FROM comments WHERE {target_col} IN ({ids_sql}) AND parent_id IS NOT NULL", **params)
    _exec(f"DELETE FROM comments WHERE {target_col} IN ({ids_sql})", **params)


def cleanup() -> dict:
    now = datetime.now(UTC)
    soft_cutoff = now - timedelta(days=90)
    stats: dict[str, int] = {}

    # Soft-deleted comments/suggestions/reviews (children first: replies before parents).
    p = {"cutoff": soft_cutoff}
    for tt, table in (("comment", "comments"), ("suggestion", "suggestions"), ("review", "harness_reviews")):
        cond = _NO_OPEN_REPORT.format(alias="x")
        extra = ""
        if table == "comments":
            extra = " AND NOT EXISTS (SELECT 1 FROM comments c2 WHERE c2.parent_id = x.id)"
        _exec(
            f"DELETE FROM votes WHERE target_type=:tt AND target_id IN "
            f"(SELECT x.id FROM {table} x WHERE x.deleted_at < :cutoff AND {cond}{extra})",
            tt=tt,
            **p,
        )
        stats[table] = _exec(
            f"DELETE FROM {table} x WHERE x.deleted_at < :cutoff AND {cond}{extra}", tt=tt, **p
        )

    # Soft-deleted top-level content.
    for tt, table, col in (
        ("harness", "harnesses", "harness_id"),
        ("idea", "ideas", "idea_id"),
        ("collection", "collections", "collection_id"),
        ("resource", "resources", "resource_id"),
    ):
        ids_sql = f"SELECT x.id FROM {table} x WHERE x.deleted_at < :cutoff AND {_NO_OPEN_REPORT.format(alias='x')}"
        params = {"cutoff": soft_cutoff, "tt": tt}
        _purge_children(col, ids_sql, params)
        if table == "collections":
            _exec(
                f"UPDATE resources SET collection_count = GREATEST(collection_count - 1, 0) WHERE id IN "
                f"(SELECT resource_id FROM collection_items WHERE collection_id IN ({ids_sql}))",
                **params,
            )
            _exec(f"DELETE FROM collection_items WHERE collection_id IN ({ids_sql})", **params)
        if table == "resources":
            _exec(
                f"UPDATE collections SET item_count = GREATEST(item_count - 1, 0) WHERE id IN "
                f"(SELECT collection_id FROM collection_items WHERE resource_id IN ({ids_sql}))",
                **params,
            )
            _exec(f"DELETE FROM collection_items WHERE resource_id IN ({ids_sql})", **params)
        _exec(f"DELETE FROM votes WHERE target_type=:tt AND target_id IN ({ids_sql})", **params)
        _exec(f"DELETE FROM bookmarks WHERE target_type=:tt AND target_id IN ({ids_sql})", **params)
        stats[table] = _exec(f"DELETE FROM {table} WHERE id IN ({ids_sql})", **params)

    # AI: deleted conversations and discarded drafts older than 30 days.
    ai_cutoff = now - timedelta(days=30)
    _exec(
        "DELETE FROM ai_messages WHERE conversation_id IN "
        "(SELECT id FROM ai_conversations WHERE deleted_at < :cutoff)",
        cutoff=ai_cutoff,
    )
    stats["ai_conversations"] = _exec("DELETE FROM ai_conversations WHERE deleted_at < :cutoff", cutoff=ai_cutoff)
    drafts = "SELECT id FROM ai_drafts WHERE status = 'discarded' AND updated_at < :cutoff"
    for table in ("harnesses", "ideas", "resources", "collections"):
        _exec(f"UPDATE {table} SET source_draft_id = NULL WHERE source_draft_id IN ({drafts})", cutoff=ai_cutoff)
    stats["ai_drafts"] = _exec(f"DELETE FROM ai_drafts WHERE id IN ({drafts})", cutoff=ai_cutoff)

    # Assistant messages left 'streaming' (client vanished before the stream started).
    stats["stale_streams"] = _exec(
        "UPDATE ai_messages SET status = 'error', error_code = 'abandoned' "
        "WHERE status = 'streaming' AND created_at < :c",
        c=now - timedelta(minutes=10),
    )

    # Orphaned votes and bookmarks.
    orphan = 0
    for tt, table in (
        ("harness", "harnesses"),
        ("idea", "ideas"),
        ("resource", "resources"),
        ("collection", "collections"),
        ("comment", "comments"),
        ("suggestion", "suggestions"),
        ("review", "harness_reviews"),
    ):
        orphan += _exec(
            f"DELETE FROM votes v WHERE v.target_type=:tt AND NOT EXISTS (SELECT 1 FROM {table} t WHERE t.id = v.target_id)",
            tt=tt,
        )
        if tt in ("harness", "idea", "resource", "collection"):
            orphan += _exec(
                f"DELETE FROM bookmarks b WHERE b.target_type=:tt AND NOT EXISTS "
                f"(SELECT 1 FROM {table} t WHERE t.id = b.target_id)",
                tt=tt,
            )
    stats["orphans"] = orphan

    stats["github_repo_cache"] = _exec("DELETE FROM github_repo_cache WHERE fetched_at < :c", c=now - timedelta(days=7))
    stats["auth_sessions"] = _exec(
        "DELETE FROM auth_sessions WHERE (revoked_at IS NOT NULL AND revoked_at < :c) "
        "OR (expires_at < :c) OR (absolute_expires_at < :c)",
        c=now - timedelta(days=30),
    )
    stats["email_tokens"] = _exec("DELETE FROM email_tokens WHERE expires_at < :c", c=now - timedelta(days=7))
    db.session.commit()
    return stats


def rebuild_counters() -> dict:
    from app.common.counters import rebuild_all

    rebuild_all()
    return {"rebuilt": True}
