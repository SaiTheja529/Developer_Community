"""auth_sessions, refresh-token rotation with reuse detection, cookies and CSRF (spec §6.5)."""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from flask import request
from sqlalchemy import delete, or_, select, update

from app.auth.models import AuthSession
from app.common.errors import ApiError
from app.extensions import db
from app.extensions import settings as get_settings

security_log = logging.getLogger("devcommons.security")

REFRESH_RACE_WINDOW = timedelta(seconds=10)
LAST_USED_UPDATE_INTERVAL = timedelta(minutes=5)


def now() -> datetime:
    return datetime.now(UTC)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits


def device_label(user_agent: str | None) -> str:
    if not user_agent:
        return "Unknown device"
    try:
        from ua_parser import parse

        r = parse(user_agent)
        browser = r.user_agent.family if r.user_agent else None
        os_name = r.os.family if r.os else None
        if browser and browser != "Other" and os_name and os_name != "Other":
            return f"{browser} on {os_name}"
        if browser and browser != "Other":
            return browser
        if os_name and os_name != "Other":
            return f"Unknown browser on {os_name}"
    except Exception:  # pragma: no cover - parser failures must never break login
        pass
    return "Unknown device"


def ip_prefix(ip: str | None) -> str | None:
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))


def create_session(user) -> tuple[AuthSession, str]:
    s = get_settings()
    raw = new_refresh_token()
    t = now()
    absolute = t + timedelta(days=s.SESSION_MAX_AGE_DAYS)
    ua = (request.headers.get("User-Agent") or "")[:300] or None
    sess = AuthSession(
        user_id=user.id,
        refresh_token_hash=hash_token(raw),
        user_agent=ua,
        device_label=device_label(ua),
        ip_prefix=ip_prefix(request.remote_addr),
        created_at=t,
        last_used_at=t,
        expires_at=min(t + timedelta(days=s.REFRESH_TOKEN_TTL_DAYS), absolute),
        absolute_expires_at=absolute,
    )
    db.session.add(sess)
    db.session.flush()
    return sess, raw


@dataclass
class RefreshOutcome:
    session: AuthSession
    raw_token: str


def rotate(raw_cookie: str | None) -> RefreshOutcome:
    """Implements the refresh steps of §6.5. Commits on success and on reuse detection."""
    if not raw_cookie:
        raise ApiError("unauthenticated", "No active session.", 401)
    h = hash_token(raw_cookie)
    sess = db.session.execute(
        select(AuthSession)
        .where(or_(AuthSession.refresh_token_hash == h, AuthSession.previous_token_hash == h))
        .with_for_update()
    ).scalar_one_or_none()
    if sess is None:
        raise ApiError("unauthenticated", "No active session.", 401, {"clear_cookie": True})

    t = now()
    if sess.revoked_at is not None or sess.expires_at <= t or sess.absolute_expires_at <= t:
        db.session.rollback()
        raise ApiError("session_revoked", "Your session has ended. Please sign in again.", 401, {"clear_cookie": True})

    if sess.refresh_token_hash != h:
        # Matched previous_token_hash.
        if sess.rotated_at is not None and t - sess.rotated_at < REFRESH_RACE_WINDOW:
            db.session.rollback()
            raise ApiError("refresh_conflict", "Session was refreshed concurrently. Retry once.", 409)
        # Token reuse => likely theft.
        sess.revoked_at = t
        sess.revoked_reason = "reuse_detected"
        user_id = sess.user_id
        db.session.commit()
        security_log.warning("refresh_token_reuse_detected", extra={"user_id": str(user_id), "session_id": str(sess.id)})
        _notify_reuse(user_id)
        raise ApiError("session_revoked", "Your session has ended. Please sign in again.", 401, {"clear_cookie": True})

    s = get_settings()
    new_raw = new_refresh_token()
    sess.previous_token_hash = sess.refresh_token_hash
    sess.refresh_token_hash = hash_token(new_raw)
    sess.rotated_at = t
    sess.last_used_at = t
    sess.expires_at = min(t + timedelta(days=s.REFRESH_TOKEN_TTL_DAYS), sess.absolute_expires_at)
    return RefreshOutcome(session=sess, raw_token=new_raw)


def _notify_reuse(user_id) -> None:
    from app.auth.email_sender import send_template
    from app.modules.users.models import User

    user = db.session.get(User, user_id)
    if user and user.email:
        send_template("suspicious_signin", user.email, {"display_name": user.display_name})


def find_session_by_cookie(raw_cookie: str | None) -> AuthSession | None:
    if not raw_cookie:
        return None
    h = hash_token(raw_cookie)
    return db.session.execute(
        select(AuthSession).where(or_(AuthSession.refresh_token_hash == h, AuthSession.previous_token_hash == h))
    ).scalar_one_or_none()


def revoke_session(sess: AuthSession, reason: str) -> None:
    if sess.revoked_at is None:
        sess.revoked_at = now()
        sess.revoked_reason = reason


def revoke_user_sessions(user_id, reason: str, except_id=None) -> int:
    stmt = (
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now(), revoked_reason=reason)
    )
    if except_id is not None:
        stmt = stmt.where(AuthSession.id != except_id)
    return db.session.execute(stmt).rowcount or 0


def delete_user_sessions(user_id) -> None:
    db.session.execute(delete(AuthSession).where(AuthSession.user_id == user_id))


# Cookies & CSRF -----------------------------------------------------------------------------


def set_refresh_cookie(response, raw_token: str) -> None:
    s = get_settings()
    response.set_cookie(
        s.REFRESH_COOKIE_NAME,
        raw_token,
        max_age=s.REFRESH_TOKEN_TTL_DAYS * 86400,
        path="/api/auth",
        secure=s.COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )


def clear_refresh_cookie(response) -> None:
    s = get_settings()
    response.delete_cookie(
        s.REFRESH_COOKIE_NAME, path="/api/auth", secure=s.COOKIE_SECURE, httponly=True, samesite="Strict"
    )


def read_refresh_cookie() -> str | None:
    return request.cookies.get(get_settings().REFRESH_COOKIE_NAME)


def enforce_csrf() -> None:
    """Cookie-authenticated endpoints require a trusted Origin and X-Requested-With: devcommons."""
    s = get_settings()
    origin = (request.headers.get("Origin") or "").rstrip("/")
    if origin not in s.CORS_ORIGINS:
        raise ApiError("forbidden", "Origin not allowed.", 403)
    if request.headers.get("X-Requested-With") != "devcommons":
        raise ApiError("forbidden", "Missing X-Requested-With header.", 403)
