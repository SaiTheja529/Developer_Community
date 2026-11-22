"""Request authentication and access decorators (spec §6.3)."""

from __future__ import annotations

import functools
import uuid
from datetime import UTC, datetime, timedelta

from flask import g, request
from sqlalchemy import select, update

from app.auth.models import AuthSession
from app.auth.tokens import decode_access_token
from app.common.errors import ApiError
from app.extensions import db
from app.modules.users.models import User

LAST_USED_INTERVAL = timedelta(minutes=5)


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if not header:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError("unauthenticated", "Malformed Authorization header.", 401)
    return token.strip()


def authenticate(strict: bool) -> None:
    """Populate g.current_user / g.session_id. With strict=False, any failure leaves the user anonymous."""
    g.current_user = None
    g.session_id = None
    g.session_created_at = None
    try:
        token = _bearer_token()
        if token is None:
            if strict:
                raise ApiError("unauthenticated", "Authentication required.", 401)
            return
        claims = decode_access_token(token)
        try:
            user_id = uuid.UUID(claims["sub"])
            session_id = uuid.UUID(claims["sid"])
        except (ValueError, KeyError) as e:
            raise ApiError("unauthenticated", "Invalid access token.", 401) from e

        row = db.session.execute(
            select(User, AuthSession)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(User.id == user_id, AuthSession.id == session_id)
        ).first()
        if row is None:
            raise ApiError("session_revoked", "Your session has ended. Please sign in again.", 401)
        user, sess = row
        now = datetime.now(UTC)
        if sess.revoked_at is not None or sess.absolute_expires_at <= now or sess.expires_at <= now:
            raise ApiError("session_revoked", "Your session has ended. Please sign in again.", 401)
        if user.status == "deleted":
            raise ApiError("unauthenticated", "Account no longer exists.", 401)
        if user.status == "suspended":
            raise ApiError("account_suspended", "This account is suspended.", 403)

        if now - sess.last_used_at > LAST_USED_INTERVAL:
            db.session.execute(update(AuthSession).where(AuthSession.id == sess.id).values(last_used_at=now))
            db.session.execute(update(User).where(User.id == user.id).values(last_seen_at=now))
            db.session.commit()
        g.current_user = user
        g.session_id = sess.id
        g.session_created_at = sess.created_at
    except ApiError:
        if strict:
            raise
        g.current_user = None
        g.session_id = None


def require_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        authenticate(strict=True)
        return fn(*args, **kwargs)

    return wrapper


def optional_auth(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        authenticate(strict=False)
        return fn(*args, **kwargs)

    return wrapper


def require_verified(fn):
    """Use *below* @require_auth. Blocks content writes and AI calls until the email is confirmed."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        user = g.get("current_user")
        if user is None:
            raise ApiError("unauthenticated", "Authentication required.", 401)
        if user.email_verified_at is None:
            raise ApiError("email_not_verified", "Confirm your email address first.", 403)
        return fn(*args, **kwargs)

    return wrapper


def require_role(role: str):
    """'moderator' allows moderators and admins; 'admin' allows admins only. Use below @require_auth."""

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            user = g.get("current_user")
            if user is None:
                raise ApiError("unauthenticated", "Authentication required.", 401)
            allowed = {"moderator": ("moderator", "admin"), "admin": ("admin",)}[role]
            if user.role not in allowed:
                raise ApiError("forbidden", "You are not allowed to do that.", 403)
            return fn(*args, **kwargs)

        return wrapper

    return deco


def current_user():
    return g.get("current_user")
