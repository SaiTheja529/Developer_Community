"""Auth business logic: registration, login with lockout, email flows, password/email change, deletion."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

from flask import jsonify
from sqlalchemy import delete, func, select, update

from app.auth import email_tokens, sessions
from app.auth.email_sender import send_template
from app.auth.models import EmailToken, OAuthAccount
from app.auth.passwords import check_password_policy, hash_password, needs_rehash, verify_password
from app.auth.tokens import issue_access_token
from app.common.errors import ApiError, validation_error
from app.extensions import db
from app.extensions import settings as get_settings
from app.modules.users.models import User
from app.modules.users.service import me_profile, username_problem

LOCKOUT_THRESHOLD = 5
LOCKOUT_WINDOW = timedelta(minutes=15)
LOCKOUT_DURATION = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(UTC)


def _link(path: str, token: str) -> str:
    return f"{get_settings().FRONTEND_URL.rstrip('/')}/{path}?token={token}"


def invalid_credentials() -> ApiError:
    return ApiError("invalid_credentials", "Incorrect email or password.", 401)


def token_response(user, session, raw_refresh: str | None, status: int = 200):
    access, ttl = issue_access_token(user, session.id)
    resp = jsonify(
        {"data": {"access_token": access, "token_type": "Bearer", "expires_in": ttl, "user": me_profile(user)}}
    )
    resp.status_code = status
    if raw_refresh:
        sessions.set_refresh_cookie(resp, raw_refresh)
    return resp


# Registration & login --------------------------------------------------------------------


def register(body) -> tuple[User, object, str]:
    email = body.email.strip().lower()
    username = body.username.strip().lower()
    problem = username_problem(username)
    if problem == "invalid":
        raise validation_error(
            {"username": "3-30 characters: lowercase letters, numbers, '_' or '-', starting with a letter or number."}
        )
    if problem == "reserved":
        raise validation_error({"username": "This username is reserved."})
    check_password_policy(body.password, email, username)
    if db.session.execute(select(User.id).where(User.email == email)).first():
        raise ApiError("email_taken", "An account with this email already exists.", 409)
    if problem == "taken":
        raise ApiError("username_taken", "This username is taken.", 409)

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        password_changed_at=_now(),
        username=username,
        display_name=body.display_name,
        last_login_at=_now(),
    )
    db.session.add(user)
    try:
        db.session.flush()
    except Exception as e:  # unique race
        db.session.rollback()
        raise ApiError("conflict", "Email or username already in use.", 409) from e
    sess, raw = sessions.create_session(user)
    token = email_tokens.issue(user, "verify_email")
    db.session.commit()
    send_template("verify_email", email, {"display_name": user.display_name, "link": _link("verify-email", token)})
    return user, sess, raw


def login(email: str, password: str) -> tuple[User, object, str]:
    email = email.strip().lower()
    user = db.session.execute(select(User).where(User.email == email).with_for_update()).scalar_one_or_none()
    if user is None or user.password_hash is None or user.status == "deleted":
        verify_password(None, password)  # equalize timing
        db.session.rollback()
        raise invalid_credentials()

    now = _now()
    if user.locked_until is not None and user.locked_until > now:
        retry = max(1, math.ceil((user.locked_until - now).total_seconds()))
        db.session.rollback()
        raise ApiError(
            "too_many_attempts",
            "Too many failed sign-in attempts. Try again later.",
            429,
            {"retry_after": retry},
            {"Retry-After": str(retry)},
        )

    if not verify_password(user.password_hash, password):
        if user.last_failed_login_at is None or now - user.last_failed_login_at > LOCKOUT_WINDOW:
            user.failed_login_count = 1
            user.last_failed_login_at = now
        else:
            user.failed_login_count += 1
        if user.failed_login_count >= LOCKOUT_THRESHOLD:
            user.locked_until = now + LOCKOUT_DURATION
            user.failed_login_count = 0
            user.last_failed_login_at = None
            db.session.commit()
            retry = int(LOCKOUT_DURATION.total_seconds())
            raise ApiError(
                "too_many_attempts",
                "Too many failed sign-in attempts. Try again later.",
                429,
                {"retry_after": retry},
                {"Retry-After": str(retry)},
            )
        db.session.commit()
        raise invalid_credentials()

    if user.status == "suspended":
        db.session.rollback()
        raise ApiError("account_suspended", "This account is suspended.", 403)

    user.failed_login_count = 0
    user.last_failed_login_at = None
    user.locked_until = None
    user.last_login_at = now
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    sess, raw = sessions.create_session(user)
    db.session.commit()
    return user, sess, raw


# Email verification ----------------------------------------------------------------------


def verify_email(raw_token: str) -> tuple[User, str]:
    tok = email_tokens.consume(raw_token, ("verify_email", "change_email"))
    user = db.session.get(User, tok.user_id)
    if user is None or user.status == "deleted":
        raise ApiError("invalid_token", "This link is invalid or has expired.", 400)
    if tok.purpose == "change_email":
        new_email = (tok.new_email or "").lower()
        taken = db.session.execute(select(User.id).where(User.email == new_email, User.id != user.id)).first()
        if taken:
            db.session.rollback()
            raise ApiError("email_taken", "An account with this email already exists.", 409)
        user.email = new_email
    user.email_verified_at = user.email_verified_at or _now()
    if tok.purpose == "change_email":
        user.email_verified_at = _now()
    db.session.commit()
    return user, tok.purpose


def resend_verification(user: User) -> None:
    if user.email_verified_at is not None or not user.email:
        raise ApiError("conflict", "Your email is already verified.", 409)
    token = email_tokens.issue(user, "verify_email")
    db.session.commit()
    send_template("verify_email", user.email, {"display_name": user.display_name, "link": _link("verify-email", token)})


# Password reset / change ------------------------------------------------------------------


def forgot_password(email: str) -> None:
    email = email.strip().lower()
    user = db.session.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None or user.status != "active":
        return
    token = email_tokens.issue(user, "reset_password")
    db.session.commit()
    send_template(
        "reset_password", user.email, {"display_name": user.display_name, "link": _link("reset-password", token)}
    )


def reset_password(raw_token: str, new_password: str) -> None:
    tok = email_tokens.consume(raw_token, ("reset_password",))
    user = db.session.get(User, tok.user_id)
    if user is None or user.status == "deleted":
        raise ApiError("invalid_token", "This link is invalid or has expired.", 400)
    check_password_policy(new_password, user.email, user.username, field="new_password")
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    user.email_verified_at = user.email_verified_at or _now()
    user.failed_login_count = 0
    user.locked_until = None
    user.last_failed_login_at = None
    sessions.revoke_user_sessions(user.id, "password_reset")
    db.session.commit()
    send_template("password_changed", user.email, {"display_name": user.display_name})


def _confirm_identity(user: User, password: str | None, field: str) -> None:
    """Password accounts confirm with the password; GitHub/Google-only accounts need a recent sign-in."""
    if user.password_hash is None:
        from app.auth.oauth import require_recent_sign_in

        require_recent_sign_in()
        return
    if not password or not verify_password(user.password_hash, password):
        raise validation_error({field: "Current password is incorrect." if field == "current_password" else "Password is incorrect."})


def change_password(user: User, current_session_id, current_password: str | None, new_password: str):
    _confirm_identity(user, current_password, "current_password")
    check_password_policy(new_password, user.email, user.username, field="new_password")
    user.password_hash = hash_password(new_password)
    user.password_changed_at = _now()
    sessions.revoke_user_sessions(user.id, "password_change", except_id=current_session_id)
    db.session.commit()
    send_template("password_changed", user.email, {"display_name": user.display_name})


def _mask_email(email: str) -> str:
    local, _, domain = email.partition("@")
    return (local[:1] + "***@" + domain) if domain else "***"


def change_email(user: User, new_email: str, password: str | None) -> None:
    _confirm_identity(user, password, "password")
    new_email = new_email.strip().lower()
    if user.email and new_email == user.email.lower():
        raise validation_error({"new_email": "This is already your email."})
    if db.session.execute(select(User.id).where(User.email == new_email)).first():
        raise ApiError("email_taken", "An account with this email already exists.", 409)
    token = email_tokens.issue(user, "change_email", new_email=new_email)
    db.session.commit()
    send_template(
        "email_change_confirm", new_email, {"display_name": user.display_name, "link": _link("verify-email", token)}
    )
    if user.email:
        send_template(
            "email_change_notice",
            user.email,
            {"display_name": user.display_name, "new_email_masked": _mask_email(new_email)},
        )


# Account deletion (§6.8) -------------------------------------------------------------------


def delete_account(user: User, password: str | None) -> None:
    from app.modules.ai.models import AIConversation, AIDraft, AIMessage
    from app.modules.collaborations.models import CollaborationRequest
    from app.modules.collections.models import Collection
    from app.modules.harnesses.models import Harness
    from app.modules.ideas.models import Idea
    from app.modules.notifications.models import Notification
    from app.modules.resources.models import Resource
    from app.modules.votes.models import Bookmark

    _confirm_identity(user, password, "password")
    uid = user.id

    # AI data: hard delete. Detach drafts from published content first (FK RESTRICT).
    draft_ids = select(AIDraft.id).where(AIDraft.user_id == uid)
    for model in (Harness, Idea, Resource, Collection):
        db.session.execute(update(model).where(model.source_draft_id.in_(draft_ids)).values(source_draft_id=None))
    db.session.execute(delete(AIDraft).where(AIDraft.user_id == uid))
    conv_ids = select(AIConversation.id).where(AIConversation.user_id == uid)
    db.session.execute(delete(AIMessage).where(AIMessage.conversation_id.in_(conv_ids)))
    db.session.execute(delete(AIConversation).where(AIConversation.user_id == uid))

    # Bookmarks, pending collaboration requests, sessions, email tokens, own notifications.
    bms = db.session.execute(select(Bookmark).where(Bookmark.user_id == uid)).scalars().all()
    from app.common.content import model_for
    from app.common.counters import bump

    for bm in bms:
        bump(model_for(bm.target_type), bm.target_id, "bookmark_count", -1)
    db.session.execute(delete(Bookmark).where(Bookmark.user_id == uid))
    db.session.execute(
        delete(CollaborationRequest).where(
            CollaborationRequest.status == "pending",
            (CollaborationRequest.requester_id == uid) | (CollaborationRequest.owner_id == uid),
        )
    )
    sessions.delete_user_sessions(uid)
    db.session.execute(delete(EmailToken).where(EmailToken.user_id == uid))
    db.session.execute(delete(OAuthAccount).where(OAuthAccount.user_id == uid))
    db.session.execute(delete(Notification).where(Notification.recipient_id == uid))

    # Anonymize the user row; community content stays, attributed to "Deleted user".
    user.status = "deleted"
    user.display_name = "Deleted user"
    user.username = f"deleted_{str(uid).replace('-', '')[:12]}"
    user.email = None
    user.email_verified_at = None
    user.password_hash = None
    user.bio = None
    user.website_url = None
    user.github_username = None
    user.contact_links = []
    user.skills = []
    user.interests = []
    user.avatar_url = None
    user.contact_visibility = "hidden"
    user.updated_at = func.now()
    db.session.commit()
