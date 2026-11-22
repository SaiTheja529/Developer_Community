"""/api/auth/* endpoints (spec §6.6)."""

from __future__ import annotations

import uuid

from flask import Blueprint, g, jsonify, make_response
from sqlalchemy import select

from app.auth import oauth, service, sessions
from app.auth.decorators import require_auth
from app.auth.models import AuthSession
from app.auth.schemas import (
    ForgotPasswordBody,
    LoginBody,
    RegisterBody,
    ResetPasswordBody,
    TokenBody,
)
from app.common.errors import ApiError, not_found
from app.common.ratelimit import client_ip, enforce, limit
from app.common.responses import accepted, ok
from app.common.validation import parse_body
from app.extensions import db
from app.modules.users.models import User

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def _clear_cookie_response(e: ApiError):
    """Errors on cookie endpoints that should also clear the refresh cookie."""
    resp = jsonify(
        {"error": {"code": e.code, "message": e.message, "request_id": g.get("request_id")}}
    )
    resp.status_code = e.status
    sessions.clear_refresh_cookie(resp)
    return resp


@bp.post("/register")
@limit("5 per hour", "auth_register", key=lambda: f"ip:{client_ip()}")
def register():
    body = parse_body(RegisterBody)
    user, sess, raw = service.register(body)
    return service.token_response(user, sess, raw, status=201)


@bp.post("/login")
@limit("10 per minute", "auth_login", key=lambda: f"ip:{client_ip()}")
def login():
    body = parse_body(LoginBody)
    user, sess, raw = service.login(body.email, body.password)
    return service.token_response(user, sess, raw)


@bp.post("/refresh")
@limit("30 per minute", "auth_refresh", key=lambda: f"ip:{client_ip()}")
def refresh():
    sessions.enforce_csrf()
    try:
        outcome = sessions.rotate(sessions.read_refresh_cookie())
    except ApiError as e:
        if e.details and e.details.get("clear_cookie"):
            return _clear_cookie_response(e)
        raise
    user = db.session.get(User, outcome.session.user_id)
    if user is None or user.status == "deleted":
        db.session.rollback()
        return _clear_cookie_response(ApiError("unauthenticated", "No active session.", 401))
    if user.status == "suspended":
        db.session.rollback()
        return _clear_cookie_response(ApiError("account_suspended", "This account is suspended.", 403))
    db.session.commit()
    return service.token_response(user, outcome.session, outcome.raw_token)


@bp.post("/logout")
def logout():
    sessions.enforce_csrf()
    sess = sessions.find_session_by_cookie(sessions.read_refresh_cookie())
    if sess is not None:
        sessions.revoke_session(sess, "logout")
        db.session.commit()
    resp = make_response("", 204)
    sessions.clear_refresh_cookie(resp)
    return resp


@bp.post("/logout-all")
@require_auth
def logout_all():
    sessions.revoke_user_sessions(g.current_user.id, "logout_all")
    db.session.commit()
    resp = make_response("", 204)
    sessions.clear_refresh_cookie(resp)
    return resp


@bp.get("/sessions")
@require_auth
def list_sessions():
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    rows = (
        db.session.execute(
            select(AuthSession)
            .where(
                AuthSession.user_id == g.current_user.id,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
                AuthSession.absolute_expires_at > now,
            )
            .order_by(AuthSession.last_used_at.desc())
        )
        .scalars()
        .all()
    )
    return ok(
        [
            {
                "id": str(s.id),
                "device_label": s.device_label or "Unknown device",
                "created_at": s.created_at,
                "last_used_at": s.last_used_at,
                "is_current": s.id == g.session_id,
            }
            for s in rows
        ]
    )


@bp.delete("/sessions/<uuid:session_id>")
@require_auth
def revoke_one_session(session_id: uuid.UUID):
    sess = db.session.get(AuthSession, session_id)
    if sess is None or sess.user_id != g.current_user.id:
        raise not_found()
    sessions.revoke_session(sess, "logout")
    db.session.commit()
    return "", 204


@bp.post("/verify-email")
def verify_email():
    body = parse_body(TokenBody)
    user, purpose = service.verify_email(body.token)
    return ok({"verified": True, "purpose": purpose, "email_verified": True})


@bp.post("/resend-verification")
@require_auth
@limit("3 per hour", "auth_resend_verification")
def resend_verification():
    service.resend_verification(g.current_user)
    return accepted({"sent": True})


_FORGOT_MESSAGE = "If an account exists for that email, we sent a link to reset the password."


@bp.post("/forgot-password")
@limit("5 per hour", "auth_forgot_ip", key=lambda: f"ip:{client_ip()}")
def forgot_password():
    body = parse_body(ForgotPasswordBody)
    try:
        enforce("3 per hour", "auth_forgot_email", key=f"email:{body.email.strip().lower()}")
    except ApiError:
        # Same response either way: never reveal whether the email exists or is throttled.
        return accepted({"message": _FORGOT_MESSAGE})
    service.forgot_password(body.email)
    return accepted({"message": _FORGOT_MESSAGE})


@bp.post("/reset-password")
def reset_password():
    body = parse_body(ResetPasswordBody)
    service.reset_password(body.token, body.new_password)
    resp = make_response("", 204)
    sessions.clear_refresh_cookie(resp)
    return resp


# Sign in with GitHub / Google ------------------------------------------------------------------


@bp.get("/providers")
def providers():
    """Which social sign-in buttons the frontend should show."""
    return ok(oauth.enabled_providers())


@bp.get("/oauth/<provider>/start")
@limit("20 per minute", "auth_oauth_start", key=lambda: f"ip:{client_ip()}")
def oauth_start(provider: str):
    return oauth.start(provider)


@bp.get("/oauth/<provider>/callback")
@limit("20 per minute", "auth_oauth_callback", key=lambda: f"ip:{client_ip()}")
def oauth_callback(provider: str):
    return oauth.callback(provider)


@bp.post("/oauth/<provider>/link")
@require_auth
@limit("10 per hour", "auth_oauth_link")
def oauth_link(provider: str):
    """Returns a 5-minute token for /oauth/<provider>/start?link=... (a browser redirect can't carry a Bearer token)."""
    oauth.get_provider(provider)
    return ok({"link_token": oauth.issue_link_token(g.current_user)})


@bp.get("/connections")
@require_auth
def list_connections():
    return ok(oauth.connections(g.current_user))


@bp.delete("/connections/<provider>")
@require_auth
def unlink_connection(provider: str):
    oauth.unlink(g.current_user, provider)
    return "", 204
